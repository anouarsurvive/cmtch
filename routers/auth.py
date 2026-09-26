# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import sys
import urllib.parse
import uuid
from datetime import date, datetime, time, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)

from core.config import (
    BASE_DIR,
    DB_PATH,
    EMAIL_FROM,
    SESSION_MAX_AGE_DAYS,
    SESSION_TIMEOUT_MINUTES,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SERVER,
    SMTP_USERNAME,
)
from core.deps import check_admin, get_current_user, require_login
from core.forms import parse_multipart_form
from core.passwords import hash_password, verify_password
from core.session import (
    cleanup_expired_sessions,
    create_secure_session_token,
    create_session_token,
    deactivate_session,
    get_db_connection,
    parse_session_token,
    update_session_activity,
    validate_session_token,
)
from core.templates import ensure_absolute_image_url, templates
from db import sql as db_sql
from security_utils import (
    COOKIE_SECURE,
    SECRET_KEY,
    needs_rehash as secure_needs_rehash,
    session_cookie_kwargs,
    hash_password as secure_hash_password,
    verify_password as secure_verify_password,
)
from services.backup import (
    auto_backup_system,
    backup_database,
    find_latest_backup,
    restore_database,
)
from services.email import (
    generate_ics_content,
    send_email,
    send_member_validation_email,
    send_reservation_confirmation_email,
)

try:
    from photo_upload_service_imgbb import upload_photo_to_imgbb, test_imgbb_system
except ImportError as e:
    print(f"Attention: Impossible d'importer photo_upload_service_imgbb: {e}")

    def upload_photo_to_imgbb(file_data: bytes, filename: str) -> Dict[str, Any]:
        return {'success': False, 'error': "Service d'upload d'images non disponible"}

    def test_imgbb_system() -> Dict[str, Any]:
        return {
            'status': 'error',
            'message': "Service d'upload d'images non disponible",
            'imgbb_working': False,
        }

router = APIRouter()

@router.get("/article_images/{filename}")
async def serve_article_image(filename: str):
    """Redirige les requÃªtes d'images d'articles vers HostGator"""
    hostgator_url = f"https://www.cmtch.online/static/article_images/{filename}"
    return RedirectResponse(url=hostgator_url, status_code=302)

@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """Page d'accueil du site.

    Affiche une prÃ©sentation du club, les coordonnÃ©es et un lien vers les
    diffÃ©rentes sections selon le rÃ´le de l'utilisateur.
    """
    user = get_current_user(request)
    # Informations publiques sur le club provenant de sources fiables.
    adresse = "Route Teboulbi km 6, 3041 Sfax sud"
    telephone = "+21627617133"
    email = "club.tennis.chihia@gmail.com"
    description = (
        "Club municipal de tennis Chihia est un lieu spÃ©cialement conÃ§u pour les personnes "
        "souhaitant pratiquer le Tennis."
    )
    # RÃ©cupÃ©rer les trois derniers articles pour les mettre en avant sur l'accueil
    conn = get_db_connection()
    
    # VÃ©rifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        from database import get_mysql_cursor_with_names, convert_mysql_result
        execute_with_names = get_mysql_cursor_with_names(conn)
        cur, column_names = execute_with_names(
            "SELECT id, title, content, image_path, created_at FROM articles ORDER BY created_at DESC LIMIT 3"
        )
        latest_articles = cur.fetchall()
        # Convertir les tuples MySQL en objets avec attributs nommÃ©s
        latest_articles = [convert_mysql_result(article, column_names) for article in latest_articles]
    else:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, content, image_path, created_at FROM articles ORDER BY created_at DESC LIMIT 3"
        )
        latest_articles = cur.fetchall()
    conn.close()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "is_admin": bool(user.is_admin) if user else False,
            "validated": bool(user.validated) if user else False,
            "adresse": adresse,
            "telephone": telephone,
            "email": email,
            "description": description,
            "latest_articles": latest_articles,
        },
    )


@router.get("/inscription", response_class=HTMLResponse)
async def registration_form(request: Request) -> HTMLResponse:
    """Affiche le formulaire d'inscription pour les nouveaux membres."""
    user = get_current_user(request)
    # Si un utilisateur est dÃ©jÃ  connectÃ©, on le redirige vers l'accueil
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "register.html",
        {"request": request},
    )


@router.post("/inscription", response_class=HTMLResponse)
async def register(request: Request) -> HTMLResponse:
    """Traite la soumission du formulaire d'inscription.

    Si le nom d'utilisateur est dÃ©jÃ  pris ou si les mots de passe ne
    correspondent pas, la page renvoie un message d'erreur.
    L'utilisateur est crÃ©Ã© avec l'attribut `validated` Ã  0 et ne pourra pas se
    connecter tant qu'un administrateur ne l'aura pas validÃ©.
    """
    try:
        # Utiliser Form pour une gestion plus robuste des donnÃ©es
        form_data = await request.form()
        
        # RÃ©cupÃ©ration des donnÃ©es du formulaire
        username = str(form_data.get("username", "")).strip()
        full_name = str(form_data.get("full_name", "")).strip()
        email = str(form_data.get("email", "")).strip()
        phone = str(form_data.get("phone", "")).strip()
        ijin_number = str(form_data.get("ijin_number", "")).strip()
        birth_date = str(form_data.get("birth_date", "")).strip()
        password = str(form_data.get("password", ""))
        confirm_password = str(form_data.get("confirm_password", ""))
        role = str(form_data.get("role", "member"))
        
        # VÃ©rifications de base
        errors: List[str] = []
        
        if not username:
            errors.append("Le nom d'utilisateur est obligatoire.")
        if not full_name:
            errors.append("Le nom complet est obligatoire.")
        if not email:
            errors.append("L'adresse eâ€‘mail est obligatoire.")
        if not phone:
            errors.append("Le tÃ©lÃ©phone est obligatoire.")
        # Le numÃ©ro IJIN n'est plus obligatoire
        # if not ijin_number:
        #     errors.append("Le numÃ©ro IJIN est obligatoire.")
        if not birth_date:
            errors.append("La date de naissance est obligatoire.")
        if not password:
            errors.append("Le mot de passe est obligatoire.")
        if password != confirm_password:
            errors.append("Les mots de passe ne correspondent pas.")
        if len(password) < 6:
            errors.append("Le mot de passe doit contenir au moins 6 caractÃ¨res.")
            
        # VÃ©rifier que le nom d'utilisateur, l'email et le tÃ©lÃ©phone n'existent pas dÃ©jÃ 
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            # VÃ©rifier le nom d'utilisateur
            cur.execute("SELECT id, username FROM users WHERE username = %s", (username,))
            existing_user = cur.fetchone()
            if existing_user:
                errors.append("Ce nom d'utilisateur est dÃ©jÃ  utilisÃ©.")
            
            # VÃ©rifier l'email
            cur.execute("SELECT id, username, email FROM users WHERE email = %s", (email,))
            existing_email = cur.fetchone()
            if existing_email:
                errors.append(f"Cette adresse email ({email}) est dÃ©jÃ  utilisÃ©e par l'utilisateur '{existing_email[1]}'. Si c'est votre compte, vous pouvez rÃ©cupÃ©rer votre mot de passe.")
            
            # VÃ©rifier le tÃ©lÃ©phone
            cur.execute("SELECT id, username, phone FROM users WHERE phone = %s", (phone,))
            existing_phone = cur.fetchone()
            if existing_phone:
                errors.append(f"Ce numÃ©ro de tÃ©lÃ©phone ({phone}) est dÃ©jÃ  utilisÃ© par l'utilisateur '{existing_phone[1]}'. Si c'est votre compte, vous pouvez rÃ©cupÃ©rer votre mot de passe.")
        else:
            cur = conn.cursor()
            # VÃ©rifier le nom d'utilisateur
            cur.execute("SELECT id, username FROM users WHERE username = ?", (username,))
            existing_user = cur.fetchone()
            if existing_user:
                errors.append("Ce nom d'utilisateur est dÃ©jÃ  utilisÃ©.")
            
            # VÃ©rifier l'email
            cur.execute("SELECT id, username, email FROM users WHERE email = ?", (email,))
            existing_email = cur.fetchone()
            if existing_email:
                errors.append(f"Cette adresse email ({email}) est dÃ©jÃ  utilisÃ©e par l'utilisateur '{existing_email[1]}'. Si c'est votre compte, vous pouvez rÃ©cupÃ©rer votre mot de passe.")
            
            # VÃ©rifier le tÃ©lÃ©phone
            cur.execute("SELECT id, username, phone FROM users WHERE phone = ?", (phone,))
            existing_phone = cur.fetchone()
            if existing_phone:
                errors.append(f"Ce numÃ©ro de tÃ©lÃ©phone ({phone}) est dÃ©jÃ  utilisÃ© par l'utilisateur '{existing_phone[1]}'. Si c'est votre compte, vous pouvez rÃ©cupÃ©rer votre mot de passe.")
            
        if errors:
            conn.close()
            return templates.TemplateResponse(
                "register.html",
                {
                    "request": request,
                    "errors": errors,
                    "username": username,
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "role": role,
                    "ijin_number": ijin_number,
                    "birth_date": birth_date,
                },
            )
            
        # CrÃ©ation de l'utilisateur
        pwd_hash = hash_password(password)
        is_trainer = 1 if role == "trainer" else 0
        
        # VÃ©rification email dÃ©sactivÃ©e - marquer directement comme vÃ©rifiÃ©
        email_verification_token = None
        email_verified = 1
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur.execute(
                "INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, photo_path, is_admin, validated, is_trainer, email_verification_token, email_verified) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, 0, %s, %s, %s)",
                (username, pwd_hash, full_name, email, phone, ijin_number, birth_date, "", is_trainer, email_verification_token, email_verified),
            )
        else:
            cur.execute(
                "INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, photo_path, is_admin, validated, is_trainer, email_verification_token, email_verified) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?)",
                (username, pwd_hash, full_name, email, phone, ijin_number, birth_date, "", is_trainer, email_verification_token, email_verified),
            )
        conn.commit()
        conn.close()
        
        print(f"âœ… Utilisateur crÃ©Ã© avec succÃ¨s: {username}")
        
        # VÃ©rification email dÃ©sactivÃ©e - redirection simple
        return templates.TemplateResponse(
            "register_success.html",
            {
                "request": request, 
                "username": username,
                "email": email,
                "verification_url": None
            },
        )
        
    except Exception as e:
        print(f"âŒ Erreur lors de l'inscription: {e}")
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "errors": [f"Une erreur s'est produite lors de l'inscription: {str(e)}"],
                "username": username if 'username' in locals() else "",
                "full_name": full_name if 'full_name' in locals() else "",
                "email": email if 'email' in locals() else "",
                "phone": phone if 'phone' in locals() else "",
                "role": role if 'role' in locals() else "member",
                "ijin_number": ijin_number if 'ijin_number' in locals() else "",
                "birth_date": birth_date if 'birth_date' in locals() else "",
            },
        )


@router.get("/verifier-email/{token}", response_class=HTMLResponse)
async def verify_email(request: Request, token: str) -> HTMLResponse:
    """Valide l'adresse email d'un utilisateur via un token."""
    try:
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, username, email, email_verified FROM users WHERE email_verification_token = %s",
                (token,)
            )
        else:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, username, email, email_verified FROM users WHERE email_verification_token = ?",
                (token,)
            )
        
        user = cur.fetchone()
        
        if not user:
            conn.close()
            return templates.TemplateResponse(
                "email_verification_error.html",
                {
                    "request": request,
                    "error": "Token de validation invalide ou expirÃ©."
                }
            )
        
        user_id, username, email, email_verified = user
        
        if email_verified:
            conn.close()
            return templates.TemplateResponse(
                "email_verification_error.html",
                {
                    "request": request,
                    "error": "Cette adresse email a dÃ©jÃ  Ã©tÃ© validÃ©e."
                }
            )
        
        # Marquer l'email comme vÃ©rifiÃ©
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur.execute(
                "UPDATE users SET email_verified = 1, email_verification_token = NULL WHERE id = %s",
                (user_id,)
            )
        else:
            cur.execute(
                "UPDATE users SET email_verified = 1, email_verification_token = NULL WHERE id = ?",
                (user_id,)
            )
        
        conn.commit()
        conn.close()
        
        return templates.TemplateResponse(
            "email_verification_success.html",
            {
                "request": request,
                "username": username,
                "email": email
            }
        )
        
    except Exception as e:
        print(f"âŒ Erreur lors de la validation email: {e}")
        return templates.TemplateResponse(
            "email_verification_error.html",
            {
                "request": request,
                "error": f"Une erreur s'est produite lors de la validation: {str(e)}"
            }
        )


@router.get("/connexion", response_class=HTMLResponse)
async def login_form(request: Request) -> HTMLResponse:
    """Affiche le formulaire de connexion."""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/connexion", response_class=HTMLResponse)
async def login(request: Request) -> HTMLResponse:
    """Valide les informations de connexion et ouvre une session."""
    try:
        # Utiliser Form pour une gestion plus robuste des donnÃ©es
        form_data = await request.form()
        username = form_data.get("username", "").strip()
        password = form_data.get("password", "")
        
        # Validation des donnÃ©es
        if not username or not password:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "errors": ["Veuillez remplir tous les champs."], "username": username},
            )
        
        # Connexion Ã  la base de donnÃ©es
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            # Utiliser le curseur MySQL avec noms de colonnes
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            cur, column_names = execute_with_names("SELECT * FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            user = convert_mysql_result(user, column_names)
        else:
            # Connexion SQLite/PostgreSQL — pattern db.sql (adapt_sql)
            cur = db_sql.execute(conn, "SELECT * FROM users WHERE username = ?", (username,))
            user = cur.fetchone()
        
        conn.close()
        
        errors: List[str] = []
        
        # VÃ©rification de l'utilisateur
        if user is None:
            errors.append("Nom d'utilisateur ou mot de passe incorrect.")
        elif not verify_password(password, user.password_hash):
            errors.append("Nom d'utilisateur ou mot de passe incorrect.")
        elif not user.validated:
            errors.append("Votre inscription n'a pas encore Ã©tÃ© validÃ©e par un administrateur.")
        # VÃ©rification email dÃ©sactivÃ©e pour l'instant
        # elif not user.get("email_verified", True) and not user.get("is_admin", False):
        #     errors.append("Votre adresse email n'a pas encore Ã©tÃ© validÃ©e. Veuillez vÃ©rifier votre boÃ®te mail et cliquer sur le lien de confirmation.")
        
        # Si erreurs, afficher le formulaire avec les erreurs
        if errors:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "errors": errors, "username": username},
            )
        
        # Connexion rÃ©ussie - crÃ©er la session sÃ©curisÃ©e
        # Migration progressive SHA-256 â†’ bcrypt
        try:
            pwd_hash = user.password_hash if hasattr(user, "password_hash") else user["password_hash"]
            user_id_val = user.id if hasattr(user, "id") else user["id"]
            if secure_needs_rehash(pwd_hash):
                new_hash = hash_password(password)
                mig_conn = get_db_connection()
                mig_cur = mig_conn.cursor()
                if hasattr(mig_conn, "_is_mysql") and mig_conn._is_mysql:
                    mig_cur.execute(
                        "UPDATE users SET password_hash = %s WHERE id = %s",
                        (new_hash, user_id_val),
                    )
                else:
                    mig_cur.execute(
                        "UPDATE users SET password_hash = ? WHERE id = ?",
                        (new_hash, user_id_val),
                    )
                mig_conn.commit()
                mig_conn.close()
        except Exception as mig_err:
            print(f"âš ï¸ Migration hash mot de passe: {mig_err}")

        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        token = create_secure_session_token(user.id, ip_address, user_agent)
        
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="session_token",
            value=token,
            **session_cookie_kwargs(60 * 60 * 24 * SESSION_MAX_AGE_DAYS),
        )
        return response
        
    except Exception as e:
        # Gestion des erreurs
        print(f"Erreur lors de la connexion: {e}")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "errors": ["Une erreur s'est produite. Veuillez rÃ©essayer."], "username": username if 'username' in locals() else ""},
        )


@router.get("/deconnexion")
async def logout(request: Request) -> RedirectResponse:
    """Termine la session de l'utilisateur."""
    token = request.cookies.get("session_token")
    if token:
        # DÃ©sactiver la session en base de donnÃ©es
        deactivate_session(token)
    
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_token")
    return response


@router.get("/admin/cleanup-sessions")
async def cleanup_sessions_admin(request: Request) -> dict:
    """Endpoint d'administration pour nettoyer les sessions expirÃ©es."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Non autorisÃ©")
    check_admin(user)
    
    try:
        cleanup_expired_sessions()
        return {"status": "success", "message": "Sessions expirÃ©es nettoyÃ©es avec succÃ¨s"}
    except Exception as e:
        return {"status": "error", "message": f"Erreur lors du nettoyage : {e}"}


@router.get("/admin/create-sessions-table")
async def create_sessions_table_admin(request: Request) -> dict:
    """Endpoint d'administration pour crÃ©er la table user_sessions."""
    # VÃ©rifier l'authentification de maniÃ¨re plus permissive
    user = get_current_user(request)
    if not user:
        # Si pas d'utilisateur, essayer de crÃ©er la table quand mÃªme (pour le dÃ©ploiement)
        print("âš ï¸ Aucun utilisateur connectÃ©, crÃ©ation de la table autorisÃ©e")
    else:
        # VÃ©rifier si c'est un admin
        try:
            check_admin(user)
        except:
            print("âš ï¸ Utilisateur non-admin, crÃ©ation de la table autorisÃ©e")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # VÃ©rifier si la table existe dÃ©jÃ 
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() AND table_name = 'user_sessions'
            """)
        else:
            cur.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='user_sessions'
            """)
        
        table_exists = cur.fetchone()[0] > 0
        
        if table_exists:
            return {"status": "info", "message": "Table user_sessions existe dÃ©jÃ "}
        
        # CrÃ©er la table
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur.execute("""
                CREATE TABLE user_sessions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    session_token VARCHAR(255) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    is_active TINYINT(1) DEFAULT 1,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            
            # CrÃ©er les index
            cur.execute("CREATE INDEX idx_sessions_token ON user_sessions(session_token)")
            cur.execute("CREATE INDEX idx_sessions_user ON user_sessions(user_id)")
            cur.execute("CREATE INDEX idx_sessions_expires ON user_sessions(expires_at)")
        else:
            cur.execute("""
                CREATE TABLE user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_token TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    last_activity TEXT NOT NULL DEFAULT (datetime('now')),
                    expires_at TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            
            # CrÃ©er les index
            cur.execute("CREATE INDEX idx_sessions_token ON user_sessions(session_token)")
            cur.execute("CREATE INDEX idx_sessions_user ON user_sessions(user_id)")
            cur.execute("CREATE INDEX idx_sessions_expires ON user_sessions(expires_at)")
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Table user_sessions crÃ©Ã©e avec succÃ¨s"}
        
    except Exception as e:
        return {"status": "error", "message": f"Erreur lors de la crÃ©ation de la table : {e}"}


@router.get("/create-sessions-table")
async def create_sessions_table_public() -> dict:
    """Endpoint public pour crÃ©er la table user_sessions (pour le dÃ©ploiement)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # VÃ©rifier si la table existe dÃ©jÃ 
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() AND table_name = 'user_sessions'
            """)
        else:
            cur.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='user_sessions'
            """)
        
        table_exists = cur.fetchone()[0] > 0
        
        if table_exists:
            return {"status": "info", "message": "Table user_sessions existe dÃ©jÃ "}
        
        # CrÃ©er la table
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur.execute("""
                CREATE TABLE user_sessions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    session_token VARCHAR(255) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    is_active TINYINT(1) DEFAULT 1,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            
            # CrÃ©er les index
            cur.execute("CREATE INDEX idx_sessions_token ON user_sessions(session_token)")
            cur.execute("CREATE INDEX idx_sessions_user ON user_sessions(user_id)")
            cur.execute("CREATE INDEX idx_sessions_expires ON user_sessions(expires_at)")
        else:
            cur.execute("""
                CREATE TABLE user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_token TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    last_activity TEXT NOT NULL DEFAULT (datetime('now')),
                    expires_at TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            
            # CrÃ©er les index
            cur.execute("CREATE INDEX idx_sessions_token ON user_sessions(session_token)")
            cur.execute("CREATE INDEX idx_sessions_user ON user_sessions(user_id)")
            cur.execute("CREATE INDEX idx_sessions_expires ON user_sessions(expires_at)")
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Table user_sessions crÃ©Ã©e avec succÃ¨s"}
        
    except Exception as e:
        return {"status": "error", "message": f"Erreur lors de la crÃ©ation de la table : {e}"}


@router.get("/espace", response_class=HTMLResponse)
async def user_dashboard(request: Request) -> HTMLResponse:
    """Page personnelle affichant les statistiques de rÃ©servation par mois.

    Cette page est accessible aux utilisateurs inscrits (membres et entraÃ®neurs)
    et affiche le nombre de sÃ©ances rÃ©servÃ©es pour chaque mois. Les donnÃ©es sont
    extraites de la table des rÃ©servations en regroupant par annÃ©e/mois.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    if not user.validated:
        return templates.TemplateResponse(
            "not_validated.html",
            {"request": request, "message": "Votre inscription doit Ãªtre validÃ©e pour accÃ©der Ã  cet espace."},
        )
    conn = get_db_connection()
    
    # VÃ©rifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        from database import get_mysql_cursor_with_names, convert_mysql_result
        execute_with_names = get_mysql_cursor_with_names(conn)
        try:
            # Regrouper par annÃ©e-mois et compter
            cur, column_names = execute_with_names(
                "SELECT substr(date, 1, 7) AS month, COUNT(*) AS count FROM reservations WHERE user_id = %s GROUP BY month ORDER BY month",
                (user.id,),
            )
            rows = cur.fetchall()
            # Convertir les tuples MySQL en objets avec attributs nommÃ©s
            rows = [convert_mysql_result(row, column_names) for row in rows]
        except Exception as e:
            print(f"âŒ Erreur dans la requÃªte SQL de /espace: {e}")
            # En cas d'erreur, retourner des donnÃ©es vides
            rows = []
        finally:
            conn.close()
    else:
        cur = conn.cursor()
        try:
            # Regrouper par annÃ©e-mois et compter
            cur.execute(
                "SELECT substr(date, 1, 7) AS month, COUNT(*) AS count FROM reservations WHERE user_id = ? GROUP BY month ORDER BY month",
                (user.id,),
            )
            rows = cur.fetchall()
        except Exception as e:
            print(f"âŒ Erreur dans la requÃªte SQL de /espace: {e}")
            # En cas d'erreur, retourner des donnÃ©es vides
            rows = []
        finally:
            conn.close()
    # Transformer les rÃ©sultats en listes pour Chart.js
    months: List[str] = []
    counts: List[int] = []
    try:
        for row in rows:
            months.append(row.month)
            counts.append(row.count)
        # PrÃ©parer les versions JSON des listes pour Chart.js
        months_js = json.dumps(months)
        counts_js = json.dumps(counts)
        # PrÃ©parer les paires pour itÃ©ration dans le template (mois, count)
        data_pairs = list(zip(months, counts))
        
        # Calculer les statistiques supplÃ©mentaires
        total_reservations = sum(counts)
        total_hours = total_reservations  # Chaque rÃ©servation = 1 heure
    except Exception as e:
        print(f"âŒ Erreur dans la transformation des donnÃ©es de /espace: {e}")
        # En cas d'erreur, utiliser des listes vides
        months = []
        counts = []
        months_js = json.dumps([])
        counts_js = json.dumps([])
        data_pairs = []
        total_reservations = 0
        total_hours = 0
    
    return templates.TemplateResponse(
        "user_dashboard.html",
        {
            "request": request,
            "user": user,
            "months": months,
            "counts": counts,
            "months_js": months_js,
            "counts_js": counts_js,
            "data_pairs": data_pairs,
            "total_reservations": total_reservations,
            "total_hours": total_hours,
        },
    )

# -----------------------------------------------------------------------------
#  Endpoint de santÃ© pour Render
# -----------------------------------------------------------------------------
