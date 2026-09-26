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

@router.get("/admin/membres", response_class=HTMLResponse)
async def admin_members(request: Request) -> HTMLResponse:
    """Page d'administration des membres.

    Permet de voir tous les utilisateurs inscrits et de valider ou
    d'invalider leur statut.  Accessible uniquement aux administrateurs.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    # RÃ©cupÃ©ration des paramÃ¨tres de pagination
    page = int(request.query_params.get("page", 1))
    per_page = int(request.query_params.get("per_page", 20))
    
    # Calcul des offsets
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Compter le nombre total de membres
    cur.execute("SELECT COUNT(*) FROM users")
    total_members = cur.fetchone()[0]
    
    # RÃ©cupÃ©rer les membres pour la page courante
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        from database import get_mysql_cursor_with_names, convert_mysql_result
        execute_with_names = get_mysql_cursor_with_names(conn)
        cur, column_names = execute_with_names(
            f"SELECT id, username, full_name, email, phone, ijin_number, birth_date, photo_path, is_admin, validated, is_trainer "
            f"FROM users ORDER BY id LIMIT {per_page} OFFSET {offset}",
            ()
        )
        members = cur.fetchall()
        # Convertir les tuples MySQL en objets avec attributs nommÃ©s
        members = [convert_mysql_result(member, column_names) for member in members]
    else:
        cur.execute(
            "SELECT id, username, full_name, email, phone, ijin_number, birth_date, photo_path, is_admin, validated, is_trainer "
            "FROM users ORDER BY id LIMIT ? OFFSET ?",
            (per_page, offset)
        )
        members = cur.fetchall()
    conn.close()
    
    # Calcul de la pagination
    total_pages = max(1, (total_members + per_page - 1) // per_page)
    has_prev = page > 1
    has_next = page < total_pages
    
    # GÃ©nÃ©rer les liens de pagination
    pagination_links = []
    if total_pages > 1:
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        
        for p in range(start_page, end_page + 1):
            pagination_links.append({
                'page': p,
                'is_current': p == page,
                'url': f"/admin/membres?page={p}&per_page={per_page}"
            })
    
    return templates.TemplateResponse(
        "admin_members.html",
        {
            "request": request,
            "user": user,
            "members": members,
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "total_members": total_members,
                "per_page": per_page,
                "has_prev": has_prev,
                "has_next": has_next,
                "prev_url": f"/admin/membres?page={page-1}&per_page={per_page}" if has_prev else None,
                "next_url": f"/admin/membres?page={page+1}&per_page={per_page}" if has_next else None,
                "links": pagination_links
            }
        },
    )


@router.get("/admin/membres/ajouter", response_class=HTMLResponse)
async def admin_add_member_form(request: Request) -> HTMLResponse:
    """Affiche le formulaire d'ajout de membre pour les administrateurs."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    return templates.TemplateResponse(
        "admin_add_member.html",
        {"request": request, "user": user},
    )


@router.post("/admin/membres/ajouter", response_class=HTMLResponse)
async def admin_add_member(request: Request) -> HTMLResponse:
    """Traite l'ajout d'un nouveau membre par un administrateur."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
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
        validated = form_data.get("validated", "0") == "1"
        email_verified = form_data.get("email_verified", "0") == "1"
        
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
                "admin_add_member.html",
                {
                    "request": request,
                    "user": user,
                    "errors": errors,
                    "username": username,
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "role": role,
                    "ijin_number": ijin_number,
                    "birth_date": birth_date,
                    "validated": validated,
                    "email_verified": email_verified,
                },
            )
            
        # CrÃ©ation de l'utilisateur
        pwd_hash = hash_password(password)
        is_trainer = 1 if role == "trainer" else 0
        is_admin = 1 if role == "admin" else 0
        
        # VÃ©rification email dÃ©sactivÃ©e - marquer directement comme vÃ©rifiÃ©
        email_verification_token = None
        email_verified = 1
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur.execute(
                "INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, photo_path, is_admin, validated, is_trainer, email_verification_token, email_verified) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (username, pwd_hash, full_name, email, phone, ijin_number, birth_date, "", is_admin, validated, is_trainer, email_verification_token, email_verified),
            )
        else:
            cur.execute(
                "INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, photo_path, is_admin, validated, is_trainer, email_verification_token, email_verified) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (username, pwd_hash, full_name, email, phone, ijin_number, birth_date, "", is_admin, validated, is_trainer, email_verification_token, email_verified),
            )
        conn.commit()
        conn.close()
        
        print(f"âœ… Membre ajoutÃ© avec succÃ¨s par l'admin: {username}")
        
        return RedirectResponse(url="/admin/membres", status_code=303)
        
    except Exception as e:
        print(f"âŒ Erreur lors de l'ajout du membre: {e}")
        return templates.TemplateResponse(
            "admin_add_member.html",
            {
                "request": request,
                "user": user,
                "errors": [f"Une erreur s'est produite lors de l'ajout du membre: {str(e)}"],
                "username": username if 'username' in locals() else "",
                "full_name": full_name if 'full_name' in locals() else "",
                "email": email if 'email' in locals() else "",
                "phone": phone if 'phone' in locals() else "",
                "role": role if 'role' in locals() else "member",
                "ijin_number": ijin_number if 'ijin_number' in locals() else "",
                "birth_date": birth_date if 'birth_date' in locals() else "",
                "validated": validated if 'validated' in locals() else False,
                "email_verified": email_verified if 'email_verified' in locals() else False,
            },
        )


@router.post("/admin/membres/valider", response_class=HTMLResponse)
async def validate_member(request: Request) -> HTMLResponse:
    """Action pour valider ou invalider un membre depuis l'interface admin."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    raw_body = await request.body()
    form = urllib.parse.parse_qs(raw_body.decode(), keep_blank_values=True)
    try:
        user_id = int(form.get("user_id", ["0"])[0])
    except ValueError:
        return RedirectResponse(url="/admin/membres", status_code=303)
    conn = get_db_connection()
    
    # VÃ©rifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        cur.execute("SELECT validated FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if row is None:
            conn.close()
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
        new_state = 0 if row[0] else 1  # MySQL retourne un tuple
        cur.execute("UPDATE users SET validated = %s WHERE id = %s", (new_state, user_id))
    else:
        cur = conn.cursor()
        cur.execute("SELECT validated FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if row is None:
            conn.close()
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
        new_state = 0 if row["validated"] else 1
        cur.execute("UPDATE users SET validated = ? WHERE id = ?", (new_state, user_id))
    
    # Si le membre vient d'Ãªtre validÃ©, envoyer un email de confirmation
    if new_state == 1:
        # RÃ©cupÃ©rer les informations du membre validÃ©
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur.execute("SELECT email, full_name FROM users WHERE id = %s", (user_id,))
            member_info = cur.fetchone()
        else:
            cur.execute("SELECT email, full_name FROM users WHERE id = ?", (user_id,))
            member_info = cur.fetchone()
        
        if member_info:
            member_email, member_name = member_info
            admin_name = user.get("full_name", "l'administrateur")
            send_member_validation_email(member_email, member_name, admin_name)
    
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/membres", status_code=303)


@router.post("/admin/membres/supprimer", response_class=HTMLResponse)
async def admin_delete_member(request: Request) -> HTMLResponse:
    """Permet Ã  un administrateur de supprimer un membre."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    try:
        form_data = await request.form()
        user_id = int(form_data.get("user_id", 0))
        
        if user_id == 0:
            return RedirectResponse(url="/admin/membres", status_code=303)
        
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            
            # VÃ©rifier que l'utilisateur existe et n'est pas admin
            cur.execute("SELECT username, is_admin FROM users WHERE id = %s", (user_id,))
            member = cur.fetchone()
            
            if not member:
                conn.close()
                return RedirectResponse(url="/admin/membres", status_code=303)
            
            if member[1]:  # MySQL retourne un tuple, is_admin est Ã  l'index 1
                conn.close()
                return RedirectResponse(url="/admin/membres", status_code=303)
            
            # Supprimer l'utilisateur
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        else:
            cur = conn.cursor()
            
            # VÃ©rifier que l'utilisateur existe et n'est pas admin
            cur.execute("SELECT username, is_admin FROM users WHERE id = ?", (user_id,))
            member = cur.fetchone()
            
            if not member:
                conn.close()
                return RedirectResponse(url="/admin/membres", status_code=303)
            
            if member['is_admin']:
                conn.close()
                return RedirectResponse(url="/admin/membres", status_code=303)
            
            # Supprimer l'utilisateur
            cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        
        conn.commit()
        conn.close()
        
        return RedirectResponse(url="/admin/membres", status_code=303)
        
    except Exception as e:
        print(f"Erreur lors de la suppression: {e}")
        return RedirectResponse(url="/admin/membres", status_code=303)


@router.post("/admin/membres/supprimer-groupe", response_class=HTMLResponse)
async def admin_delete_members_bulk(request: Request) -> HTMLResponse:
    """Permet Ã  un administrateur de supprimer plusieurs membres en lot."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    try:
        form_data = await request.form()
        user_ids = form_data.getlist("user_ids")
        
        if not user_ids:
            return RedirectResponse(url="/admin/membres", status_code=303)
        
        # Convertir en entiers et filtrer les valeurs invalides
        valid_user_ids = []
        for user_id_str in user_ids:
            try:
                user_id = int(user_id_str)
                if user_id > 0:
                    valid_user_ids.append(user_id)
            except ValueError:
                continue
        
        if not valid_user_ids:
            return RedirectResponse(url="/admin/membres", status_code=303)
        
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            
            # VÃ©rifier que les utilisateurs existent et ne sont pas admin
            placeholders = ','.join(['%s' for _ in valid_user_ids])
            cur.execute(f"SELECT id, username, is_admin FROM users WHERE id IN ({placeholders})", valid_user_ids)
            members = cur.fetchall()
            
            # Filtrer les membres non-admin (MySQL retourne des tuples)
            non_admin_members = [m for m in members if not m[2]]  # is_admin est Ã  l'index 2
            non_admin_ids = [m[0] for m in non_admin_members]  # id est Ã  l'index 0
            
            if non_admin_ids:
                # Supprimer les membres non-admin
                placeholders = ','.join(['%s' for _ in non_admin_ids])
                cur.execute(f"DELETE FROM users WHERE id IN ({placeholders})", non_admin_ids)
                conn.commit()
                
                print(f"âœ… {len(non_admin_ids)} membres supprimÃ©s en lot")
        else:
            cur = conn.cursor()
            
            # VÃ©rifier que les utilisateurs existent et ne sont pas admin
            placeholders = ','.join(['?' for _ in valid_user_ids])
            cur.execute(f"SELECT id, username, is_admin FROM users WHERE id IN ({placeholders})", valid_user_ids)
            members = cur.fetchall()
            
            # Filtrer les membres non-admin
            non_admin_members = [m for m in members if not m['is_admin']]
            non_admin_ids = [m['id'] for m in non_admin_members]
            
            if non_admin_ids:
                # Supprimer les membres non-admin
                placeholders = ','.join(['?' for _ in non_admin_ids])
                cur.execute(f"DELETE FROM users WHERE id IN ({placeholders})", non_admin_ids)
                conn.commit()
                
                print(f"âœ… {len(non_admin_ids)} membres supprimÃ©s en lot")
        
        conn.close()
        
        return RedirectResponse(url="/admin/membres", status_code=303)
        
    except Exception as e:
        print(f"Erreur lors de la suppression groupÃ©e: {e}")
        return RedirectResponse(url="/admin/membres", status_code=303)


@router.get("/admin/membres/{member_id}/details")
async def admin_member_details(request: Request, member_id: int):
    """Retourne les dÃ©tails d'un membre en JSON pour le modal."""
    user = get_current_user(request)
    if not user:
        return {"status": "error", "message": "Non autorisÃ©"}
    check_admin(user)
    
    try:
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            cur, column_names = execute_with_names("SELECT * FROM users WHERE id = %s", (member_id,))
            member = cur.fetchone()
            member = convert_mysql_result(member, column_names)
        else:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = ?", (member_id,))
            member = cur.fetchone()
        
        conn.close()
        
        if not member:
            return {"status": "error", "message": "Membre non trouvÃ©"}
        
        # GÃ©nÃ©rer le HTML pour le modal
        html = f"""
        <div class="member-details-content">
            <div class="row">
                <div class="col-md-6">
                    <h6>Informations personnelles</h6>
                    <p><strong>Nom complet:</strong> {member['full_name']}</p>
                    <p><strong>Nom d'utilisateur:</strong> {member['username']}</p>
                    <p><strong>Email:</strong> {member['email'] or 'Non renseignÃ©'}</p>
                    <p><strong>TÃ©lÃ©phone:</strong> {member['phone'] or 'Non renseignÃ©'}</p>
                </div>
                <div class="col-md-6">
                    <h6>Informations supplÃ©mentaires</h6>
                    <p><strong>NumÃ©ro IJIN:</strong> {member['ijin_number'] or 'Non renseignÃ©'}</p>
                    <p><strong>Date de naissance:</strong> {member['birth_date'] or 'Non renseignÃ©e'}</p>
                    <p><strong>RÃ´le:</strong> {'Administrateur' if member['is_admin'] else 'EntraÃ®neur' if member['is_trainer'] else 'Membre'}</p>
                    <p><strong>Statut:</strong> {'ValidÃ©' if member['validated'] else 'En attente'}</p>
                </div>
            </div>
        </div>
        """
        
        return {"status": "success", "html": html}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/admin/membres/{member_id}/edit", response_class=HTMLResponse)
async def admin_edit_member_form(request: Request, member_id: int) -> HTMLResponse:
    """Affiche le formulaire d'Ã©dition d'un membre."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    try:
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            cur, column_names = execute_with_names("SELECT * FROM users WHERE id = %s", (member_id,))
            member = cur.fetchone()
            member = convert_mysql_result(member, column_names)
        else:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = ?", (member_id,))
            member = cur.fetchone()
        
        conn.close()
        
        if not member:
            raise HTTPException(status_code=404, detail="Membre non trouvÃ©")
        
        return templates.TemplateResponse(
            "admin_member_edit.html",
            {
                "request": request,
                "user": user,
                "member": member,
                "errors": []
            },
        )
        
    except Exception as e:
        print(f"Erreur lors de l'Ã©dition: {e}")
        return RedirectResponse(url="/admin/membres", status_code=303)


@router.post("/admin/membres/{member_id}/edit", response_class=HTMLResponse)
async def admin_edit_member(request: Request, member_id: int) -> HTMLResponse:
    """Traite la soumission du formulaire d'Ã©dition d'un membre."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    try:
        form_data = await request.form()
        
        # RÃ©cupÃ©ration des donnÃ©es du formulaire
        username = str(form_data.get("username", "")).strip()
        full_name = str(form_data.get("full_name", "")).strip()
        email = str(form_data.get("email", "")).strip()
        phone = str(form_data.get("phone", "")).strip()
        ijin_number = str(form_data.get("ijin_number", "")).strip()
        birth_date = str(form_data.get("birth_date", "")).strip()
        new_password = str(form_data.get("new_password", "")).strip()
        is_admin = bool(form_data.get("is_admin"))
        validated = bool(form_data.get("validated"))
        is_trainer = bool(form_data.get("is_trainer"))
        
        # VÃ©rifications de base
        errors: List[str] = []
        
        if not username:
            errors.append("Le nom d'utilisateur est obligatoire.")
        if not full_name:
            errors.append("Le nom complet est obligatoire.")
        
        # VÃ©rifier que le nom d'utilisateur n'existe pas dÃ©jÃ  (sauf pour le membre actuel)
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = %s AND id != %s", (username, member_id))
        else:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = ? AND id != ?", (username, member_id))
        
        if cur.fetchone():
            errors.append("Ce nom d'utilisateur est dÃ©jÃ  utilisÃ© par un autre membre.")
        
        if errors:
            # RÃ©cupÃ©rer les donnÃ©es du membre pour rÃ©afficher le formulaire
            if hasattr(conn, '_is_mysql') and conn._is_mysql:
                from database import get_mysql_cursor_with_names, convert_mysql_result
                execute_with_names = get_mysql_cursor_with_names(conn)
                cur, column_names = execute_with_names("SELECT * FROM users WHERE id = %s", (member_id,))
                member = cur.fetchone()
                member = convert_mysql_result(member, column_names)
            else:
                cur.execute("SELECT * FROM users WHERE id = ?", (member_id,))
                member = cur.fetchone()
            
            conn.close()
            
            return templates.TemplateResponse(
                "admin_member_edit.html",
                {
                    "request": request,
                    "user": user,
                    "member": member,
                    "errors": errors
                },
            )
        
        # Mise Ã  jour du membre
        update_fields = []
        update_values = []
        
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            update_fields.append("username = %s")
            update_fields.append("full_name = %s")
            update_fields.append("email = %s")
            update_fields.append("phone = %s")
            update_fields.append("ijin_number = %s")
            update_fields.append("birth_date = %s")
            update_fields.append("is_admin = %s")
            update_fields.append("validated = %s")
            update_fields.append("is_trainer = %s")
        else:
            update_fields.append("username = ?")
            update_fields.append("full_name = ?")
            update_fields.append("email = ?")
            update_fields.append("phone = ?")
            update_fields.append("ijin_number = ?")
            update_fields.append("birth_date = ?")
            update_fields.append("is_admin = ?")
            update_fields.append("validated = ?")
            update_fields.append("is_trainer = ?")
        
        update_values.append(username)
        update_values.append(full_name)
        update_values.append(email)
        update_values.append(phone)
        update_values.append(ijin_number)
        update_values.append(birth_date)
        update_values.append(1 if is_admin else 0)
        update_values.append(1 if validated else 0)
        update_values.append(1 if is_trainer else 0)
        
        # Si un nouveau mot de passe est fourni
        if new_password:
            if len(new_password) < 6:
                errors.append("Le mot de passe doit contenir au moins 6 caractÃ¨res.")
            else:
                if hasattr(conn, '_is_mysql') and conn._is_mysql:
                    update_fields.append("password_hash = %s")
                else:
                    update_fields.append("password_hash = ?")
                update_values.append(hash_password(new_password))
        
        if errors:
            # RÃ©cupÃ©rer les donnÃ©es du membre pour rÃ©afficher le formulaire
            if hasattr(conn, '_is_mysql') and conn._is_mysql:
                from database import get_mysql_cursor_with_names, convert_mysql_result
                execute_with_names = get_mysql_cursor_with_names(conn)
                cur, column_names = execute_with_names("SELECT * FROM users WHERE id = %s", (member_id,))
                member = cur.fetchone()
                member = convert_mysql_result(member, column_names)
            else:
                cur.execute("SELECT * FROM users WHERE id = ?", (member_id,))
                member = cur.fetchone()
            
                conn.close()
            
                return templates.TemplateResponse(
                "admin_member_edit.html",
                    {
                        "request": request,
                    "user": user,
                    "member": member,
                    "errors": errors
                },
            )
        
        # Ajouter l'ID du membre Ã  la fin pour la clause WHERE
        update_values.append(member_id)
        
        # ExÃ©cuter la mise Ã  jour
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        else:
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
        
        cur.execute(query, update_values)
        conn.commit()
        conn.close()
        
        print(f"âœ… Membre {username} mis Ã  jour avec succÃ¨s")
        
        return RedirectResponse(url="/admin/membres", status_code=303)
        
    except Exception as e:
        print(f"âŒ Erreur lors de la mise Ã  jour du membre: {e}")
        return RedirectResponse(url="/admin/membres", status_code=303)


@router.get("/admin/reservations", response_class=HTMLResponse)
async def admin_reservations(request: Request) -> HTMLResponse:
    """Affiche toutes les rÃ©servations pour les administrateurs avec pagination."""
    try:
        # 1. VÃ©rifier l'utilisateur
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/connexion", status_code=303)
        
        # 2. VÃ©rifier les droits admin
        if not user.is_admin:
                return templates.TemplateResponse(
                    "error.html",
                    {
                        "request": request,
                    "status_code": 403,
                    "detail": "AccÃ¨s rÃ©servÃ© Ã  l'administration. Vous devez Ãªtre administrateur."
                    },
                status_code=403
                )
            
        # 3. RÃ©cupÃ©ration des paramÃ¨tres de pagination
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 20))
            
        # Calcul des offsets
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cur = conn.cursor()
                
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            
            # Compter le nombre total de rÃ©servations
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM reservations")
            total_bookings = cur.fetchone()[0]
            
            # RÃ©cupÃ©rer les rÃ©servations pour la page courante avec informations utilisateur
            cur, column_names = execute_with_names(f"""
                SELECT r.*, u.username, u.full_name as user_full_name 
                FROM reservations r 
                JOIN users u ON r.user_id = u.id 
                ORDER BY r.date DESC, r.start_time DESC 
                LIMIT {per_page} OFFSET {offset}
            """, ())
            bookings = cur.fetchall()
            # Convertir les tuples MySQL en objets avec attributs nommÃ©s
            bookings = [convert_mysql_result(booking, column_names) for booking in bookings]
        else:
            cur = conn.cursor()
            
            # Compter le nombre total de rÃ©servations
            cur.execute("SELECT COUNT(*) FROM reservations")
            total_bookings = cur.fetchone()[0]
            
            # RÃ©cupÃ©rer les rÃ©servations pour la page courante avec informations utilisateur
            cur.execute("""
                SELECT r.*, u.username, u.full_name as user_full_name 
                FROM reservations r 
                JOIN users u ON r.user_id = u.id 
                ORDER BY r.date DESC, r.start_time DESC 
                LIMIT ? OFFSET ?
            """, (per_page, offset))
            bookings = cur.fetchall()
        conn.close()
        
        # Convertir les dates en chaÃ®nes pour la compatibilitÃ© avec le template
        for booking in bookings:
            if hasattr(booking.date, 'isoformat'):
                booking.date = booking.date.isoformat()
            if hasattr(booking.start_time, 'strftime'):
                booking.start_time = booking.start_time.strftime('%H:%M')
            if hasattr(booking.end_time, 'strftime'):
                booking.end_time = booking.end_time.strftime('%H:%M')
        
        # Calcul de la pagination
        total_pages = max(1, (total_bookings + per_page - 1) // per_page)
        has_prev = page > 1
        has_next = page < total_pages
        
        # GÃ©nÃ©rer les liens de pagination
        pagination_links = []
        if total_pages > 1:
            start_page = max(1, page - 2)
            end_page = min(total_pages, page + 2)
            
            for p in range(start_page, end_page + 1):
                pagination_links.append({
                    'page': p,
                    'is_current': p == page,
                    'url': f"/admin/reservations?page={p}&per_page={per_page}"
                })
            
        return templates.TemplateResponse(
            "admin_reservations.html",
            {
                "request": request,
                "user": user,
                "bookings": bookings,
                "pagination": {
                    "current_page": page,
                    "total_pages": total_pages,
                    "total_bookings": total_bookings,
                    "per_page": per_page,
                    "has_prev": has_prev,
                    "has_next": has_next,
                    "prev_url": f"/admin/reservations?page={page-1}&per_page={per_page}" if has_prev else None,
                    "next_url": f"/admin/reservations?page={page+1}&per_page={per_page}" if has_next else None,
                    "links": pagination_links
                },
                "today": date.today().isoformat(),
            },
            )
        
    except Exception as e:
        print(f"âŒ Erreur dans admin_reservations: {e}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "status_code": 500,
                "detail": f"Erreur lors du chargement des rÃ©servations: {str(e)}"
            },
            status_code=500
        )


@router.post("/admin/reservations/supprimer", response_class=HTMLResponse)
async def admin_delete_reservation(request: Request) -> HTMLResponse:
    """Permet Ã  un administrateur de supprimer une rÃ©servation."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    raw_body = await request.body()
    form = urllib.parse.parse_qs(raw_body.decode(), keep_blank_values=True)
    try:
        booking_id = int(form.get("booking_id", ["0"])[0])
    except ValueError:
        return RedirectResponse(url="/admin/reservations", status_code=303)
    conn = get_db_connection()
    
    # VÃ©rifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        cur.execute("DELETE FROM reservations WHERE id = %s", (booking_id,))
    else:
        cur = conn.cursor()
        cur.execute("DELETE FROM reservations WHERE id = ?", (booking_id,))
    
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/reservations", status_code=303)


@router.post("/admin/reservations/supprimer-lot", response_class=HTMLResponse)
async def admin_delete_reservations_bulk(request: Request) -> HTMLResponse:
    """Permet Ã  un administrateur de supprimer plusieurs rÃ©servations en lot."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    try:
        form_data = await request.form()
        booking_ids = form_data.getlist("booking_ids")
        
        if not booking_ids:
            return RedirectResponse(url="/admin/reservations", status_code=303)
        
        # Convertir en entiers et valider
        valid_ids = []
        for booking_id in booking_ids:
            try:
                valid_ids.append(int(booking_id))
            except ValueError:
                continue
        
        if not valid_ids:
            return RedirectResponse(url="/admin/reservations", status_code=303)
        
        # Supprimer les rÃ©servations
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            
            # Utiliser une requÃªte avec IN pour supprimer en lot
            placeholders = ','.join(['%s' for _ in valid_ids])
            cur.execute(f"DELETE FROM reservations WHERE id IN ({placeholders})", valid_ids)
        else:
            cur = conn.cursor()
            
            # Utiliser une requÃªte avec IN pour supprimer en lot
            placeholders = ','.join(['?' for _ in valid_ids])
            cur.execute(f"DELETE FROM reservations WHERE id IN ({placeholders})", valid_ids)
        
        deleted_count = cur.rowcount
        conn.commit()
        conn.close()
        
        print(f"âœ… {deleted_count} rÃ©servation(s) supprimÃ©e(s) en lot")
        
    except Exception as e:
        print(f"âŒ Erreur lors de la suppression en lot: {e}")
    
    return RedirectResponse(url="/admin/reservations", status_code=303)


@router.post("/admin/reservations/annuler-lot", response_class=HTMLResponse)
async def admin_cancel_reservations_bulk(request: Request) -> HTMLResponse:
    """Permet Ã  un administrateur d'annuler plusieurs rÃ©servations en lot (les supprime)."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    try:
        form_data = await request.form()
        booking_ids = form_data.getlist("booking_ids")
        
        if not booking_ids:
            return RedirectResponse(url="/admin/reservations", status_code=303)
        
        # Convertir en entiers et valider
        valid_ids = []
        for booking_id in booking_ids:
            try:
                valid_ids.append(int(booking_id))
            except ValueError:
                continue
        
        if not valid_ids:
            return RedirectResponse(url="/admin/reservations", status_code=303)
        
        # Supprimer les rÃ©servations (annulation = suppression)
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            
            # Utiliser une requÃªte avec IN pour supprimer en lot
            placeholders = ','.join(['%s' for _ in valid_ids])
            cur.execute(f"DELETE FROM reservations WHERE id IN ({placeholders})", valid_ids)
        else:
            cur = conn.cursor()
            
            # Utiliser une requÃªte avec IN pour supprimer en lot
            placeholders = ','.join(['?' for _ in valid_ids])
            cur.execute(f"DELETE FROM reservations WHERE id IN ({placeholders})", valid_ids)
        
        cancelled_count = cur.rowcount
        conn.commit()
        conn.close()
        
        print(f"âœ… {cancelled_count} rÃ©servation(s) annulÃ©e(s) en lot")
        
    except Exception as e:
        print(f"âŒ Erreur lors de l'annulation en lot: {e}")
    
    return RedirectResponse(url="/admin/reservations", status_code=303)


@router.get("/admin/reservations/export")
async def admin_export_reservations(request: Request):
    """Exporte toutes les rÃ©servations au format CSV."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # RÃ©cupÃ©rer toutes les rÃ©servations avec les informations utilisateur
        cur.execute("""
            SELECT r.id, r.date, r.start_time, r.end_time, r.court_number,
                   u.username, u.full_name, u.email, u.phone
            FROM reservations r 
            JOIN users u ON r.user_id = u.id 
            ORDER BY r.date DESC, r.start_time DESC
        """)
        reservations = cur.fetchall()
        conn.close()
        
        # CrÃ©er le contenu CSV
        csv_content = "ID,Date,DÃ©but,Fin,Court,Utilisateur,Nom complet,Email,TÃ©lÃ©phone\n"
        
        for res in reservations:
            csv_content += f"{res[0]},{res[1]},{res[2]},{res[3]},{res[4]},{res[5]},{res[6]},{res[7] or ''},{res[8] or ''}\n"
        
        # GÃ©nÃ©rer le nom de fichier avec la date
        from datetime import datetime
        filename = f"reservations_cmtch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        print(f"âŒ Erreur lors de l'export: {e}")
    return RedirectResponse(url="/admin/reservations", status_code=303)



# -----------------------------------------------------------------------------
#  Section Articles
# -----------------------------------------------------------------------------
