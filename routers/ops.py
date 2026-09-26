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

@router.get("/test-espace-simple")
async def test_espace_simple(request: Request) -> JSONResponse:
    """Test simple pour diagnostiquer le problÃ¨me de /espace."""
    try:
        # Test 1: RÃ©cupÃ©ration du cookie
        token = request.cookies.get("session_token")
        if not token:
            return JSONResponse({"error": "Aucun token de session trouvÃ©"})
        
        # Test 2: Parsing du token
        user_id = parse_session_token(token)
        if not user_id:
            return JSONResponse({"error": "Token de session invalide"})
        
        # Test 3: RÃ©cupÃ©ration de l'utilisateur
        user = get_current_user(request)
        if not user:
            return JSONResponse({"error": "get_current_user retourne None", "user_id": user_id})
        
        # Test 4: VÃ©rification des attributs
        user_attrs = {}
        try:
            user_attrs["id"] = user.id
        except Exception as e:
            user_attrs["id_error"] = str(e)
        
        try:
            user_attrs["username"] = user.username
        except Exception as e:
            user_attrs["username_error"] = str(e)
        
        try:
            user_attrs["validated"] = user.validated
        except Exception as e:
            user_attrs["validated_error"] = str(e)
        
        try:
            user_attrs["is_admin"] = user.is_admin
        except Exception as e:
            user_attrs["is_admin_error"] = str(e)
        
        # Test 5: VÃ©rification du type d'objet
        user_type = type(user).__name__
        user_dir = dir(user)
        
        return JSONResponse({
            "success": True,
            "user_id": user_id,
            "user_type": user_type,
            "user_attributes": user_attrs,
            "has_id": hasattr(user, 'id'),
            "has_validated": hasattr(user, 'validated'),
            "has_is_admin": hasattr(user, 'is_admin')
        })
        
    except Exception as e:
        import traceback
        return JSONResponse({
            "error": str(e),
            "traceback": traceback.format_exc()
        })



@router.get("/test-db-espace")
async def test_db_espace(request: Request) -> JSONResponse:
    """Test de la base de donnÃ©es pour /espace."""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"error": "Utilisateur non connectÃ©"})
        
        conn = get_db_connection()
        
        # Test simple de la base
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM reservations WHERE user_id = %s", (user.id,))
            count = cur.fetchone()[0]
            conn.close()
            
            return JSONResponse({
                "success": True,
                "database_type": "MySQL",
                "reservations_count": count,
                "user_id": user.id
            })
        else:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM reservations WHERE user_id = ?", (user.id,))
            count = cur.fetchone()[0]
            conn.close()
            
            return JSONResponse({
                "success": True,
                "database_type": "SQLite/PostgreSQL",
                "reservations_count": count,
                "user_id": user.id
            })
            
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "traceback": str(e.__traceback__)
        })

@router.get("/health")
async def health_check():
    """Point de terminaison de santÃ© pour vÃ©rifier l'Ã©tat de l'application et de la base de donnÃ©es."""
    try:
        conn = get_db_connection()
        users_count = db_sql.fetch_count(conn, "SELECT COUNT(*) FROM users")
        reservations_count = db_sql.fetch_count(conn, "SELECT COUNT(*) FROM reservations")
        articles_count = db_sql.fetch_count(conn, "SELECT COUNT(*) FROM articles")
        conn.close()
        
        return {
            "status": "healthy",
            "database": {
                "users": users_count,
                "reservations": reservations_count,
                "articles": articles_count
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/init-articles")
async def init_articles_endpoint():
    """Point de terminaison pour crÃ©er des articles de test (dÃ©bogage uniquement)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # VÃ©rifier s'il y a dÃ©jÃ  des articles
        cur.execute("SELECT COUNT(*) FROM articles")
        existing_articles = cur.fetchone()[0]
        
        if existing_articles > 0:
            return {
                "status": "info", 
                "message": f"Il y a dÃ©jÃ  {existing_articles} article(s) dans la base de donnÃ©es. Utilisez /clear-articles pour les supprimer d'abord."
            }
        
        # Articles de test avec des dates rÃ©centes
        test_articles = [
            {
                "title": "Ouverture de la saison 2025",
                "content": "Le Club Municipal de Tennis Chihia est ravi d'annoncer l'ouverture de la saison 2025. Cette annÃ©e promet d'Ãªtre exceptionnelle avec de nouveaux Ã©quipements et des programmes d'entraÃ®nement amÃ©liorÃ©s pour tous les niveaux.",
                "created_at": (datetime.now() - timedelta(days=2)).isoformat()
            },
            {
                "title": "Nouveau programme pour les jeunes",
                "content": "Nous lanÃ§ons un nouveau programme spÃ©cialement conÃ§u pour les jeunes de 8 Ã  16 ans. Ce programme combine technique, tactique et plaisir pour dÃ©velopper la passion du tennis chez nos futurs champions.",
                "created_at": (datetime.now() - timedelta(days=5)).isoformat()
            },
            {
                "title": "Tournoi interne du mois",
                "content": "Le tournoi interne du mois de janvier aura lieu le week-end prochain. Tous les membres sont invitÃ©s Ã  participer. Inscriptions ouvertes jusqu'Ã  vendredi soir.",
                "created_at": (datetime.now() - timedelta(days=8)).isoformat()
            },
            {
                "title": "Maintenance des courts",
                "content": "Nos courts de tennis ont Ã©tÃ© entiÃ¨rement rÃ©novÃ©s pendant les vacances. Nouvelle surface, filets neufs et Ã©clairage amÃ©liorÃ© pour une expÃ©rience de jeu optimale.",
                "created_at": (datetime.now() - timedelta(days=12)).isoformat()
            },
            {
                "title": "Bienvenue aux nouveaux membres",
                "content": "Nous souhaitons la bienvenue Ã  tous nos nouveaux membres qui ont rejoint le club ce mois-ci. N'hÃ©sitez pas Ã  participer aux activitÃ©s et Ã  vous intÃ©grer dans notre communautÃ© tennis.",
                "created_at": (datetime.now() - timedelta(days=15)).isoformat()
            }
        ]
        
        # InsÃ©rer les articles
        for article in test_articles:
            # VÃ©rifier si c'est une connexion MySQL
            if hasattr(conn, '_is_mysql') and conn._is_mysql:
                cur.execute("""
                    INSERT INTO articles (title, content, created_at)
                    VALUES (%s, %s, %s)
                """, (article["title"], article["content"], article["created_at"]))
            else:
                cur.execute("""
                    INSERT INTO articles (title, content, created_at)
                    VALUES (?, ?, ?)
                """, (article["title"], article["content"], article["created_at"]))
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success", 
            "message": f"{len(test_articles)} articles crÃ©Ã©s",
            "articles": [article["title"] for article in test_articles]
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/init-database")
async def init_database_endpoint():
    """Point de terminaison pour initialiser manuellement la base de donnÃ©es."""
    try:
        from database import init_db
        
        print("ðŸ”„ Initialisation manuelle de la base de donnÃ©es...")
        init_db()
        
        return {
            "status": "success",
            "message": "Base de donnÃ©es initialisÃ©e avec succÃ¨s"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de l'initialisation: {str(e)}"
        }

# -----------------------------------------------------------------------------
#  Endpoints ops / diagnostic (bloquÃ©s par dÃ©faut via security_middleware)
# -----------------------------------------------------------------------------
@router.get("/diagnostic-db")
async def diagnostic_db():
    """Point de terminaison de diagnostic pour vÃ©rifier l'Ã©tat de la base de donnÃ©es."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # VÃ©rifier si les tables existent
        tables_info = {}
        
        try:
            cur.execute("SELECT COUNT(*) FROM users")
            users_count = cur.fetchone()[0]
            tables_info["users"] = {"exists": True, "count": users_count}
        except Exception as e:
            tables_info["users"] = {"exists": False, "error": str(e)}
        
        try:
            cur.execute("SELECT COUNT(*) FROM reservations")
            reservations_count = cur.fetchone()[0]
            tables_info["reservations"] = {"exists": True, "count": reservations_count}
        except Exception as e:
            tables_info["reservations"] = {"exists": False, "error": str(e)}
        
        try:
            cur.execute("SELECT COUNT(*) FROM articles")
            articles_count = cur.fetchone()[0]
            tables_info["articles"] = {"exists": True, "count": articles_count}
        except Exception as e:
            tables_info["articles"] = {"exists": False, "error": str(e)}
        
        # VÃ©rifier l'utilisateur admin
        admin_info = {}
        try:
            cur.execute("SELECT * FROM users WHERE username = 'admin'")
            admin_user = cur.fetchone()
            if admin_user:
                admin_info = {
                    "exists": True,
                    "is_admin": bool(admin_user['is_admin']),
                    "validated": bool(admin_user['validated'])
                }
            else:
                admin_info = {"exists": False}
        except Exception as e:
            admin_info = {"exists": False, "error": str(e)}
        
        conn.close()
        
        return {
            "status": "success",
            "database_info": {
                "tables": tables_info,
                "admin_user": admin_info
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/debug-auth")
async def debug_auth(request: Request):
    """Point de terminaison de dÃ©bogage pour vÃ©rifier l'Ã©tat de l'authentification."""
    try:
        user = get_current_user(request)
        
        if user:
            return {
                "status": "connected",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "is_admin": bool(user.is_admin),
                    "validated": bool(user.validated),
                    "is_trainer": bool(user.is_trainer)
                },
                "message": "Utilisateur connectÃ©"
            }
        else:
            return {
                "status": "not_connected",
                "message": "Aucun utilisateur connectÃ©"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur: {str(e)}"
        }


@router.get("/fix-admin")
async def fix_admin_endpoint():
    """Point de terminaison pour crÃ©er/corriger l'utilisateur admin UNIQUEMENT si nÃ©cessaire."""
    try:
        # D'abord, initialiser la base de donnÃ©es si nÃ©cessaire
        from database import init_db
        init_db()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # VÃ©rifier si l'utilisateur admin existe
        cur.execute("SELECT * FROM users WHERE username = 'admin'")
        admin_user = cur.fetchone()
        
        if admin_user:
            # Corriger les permissions si nÃ©cessaire
            updates = []
            
            if not admin_user[9]:  # is_admin est Ã  l'index 9
                cur.execute("UPDATE users SET is_admin = 1 WHERE username = 'admin'")
                updates.append("droits admin ajoutÃ©s")
            
            if not admin_user[10]:  # validated est Ã  l'index 10
                cur.execute("UPDATE users SET validated = 1 WHERE username = 'admin'")
                updates.append("statut validÃ© ajoutÃ©")
            
            # Mettre Ã  jour le mot de passe
            admin_password = "admin"
            admin_password_hash = hash_password(admin_password)
            
            if admin_user[2] != admin_password_hash:  # password_hash est Ã  l'index 2
                cur.execute("UPDATE users SET password_hash = %s WHERE username = 'admin'", (admin_password_hash,))
                updates.append("mot de passe mis Ã  jour")
            
            conn.commit()
            
            if updates:
                return {
                    "status": "success",
                    "message": f"Utilisateur admin corrigÃ©: {', '.join(updates)}",
                    "note": "Identifiants non renvoyÃ©s. Changez le mot de passe admin immÃ©diatement.",
                }
            else:
                return {
                    "status": "success",
                    "message": "Utilisateur admin dÃ©jÃ  correct",
                }
        else:
            # CrÃ©er l'utilisateur admin
            admin_password = "admin"
            admin_password_hash = hash_password(admin_password)
            
            # VÃ©rifier si c'est une connexion MySQL
            if hasattr(conn, '_is_mysql') and conn._is_mysql:
                cur.execute("""
                    INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, is_admin, validated, is_trainer, email_verification_token, email_verified)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, ("admin", admin_password_hash, "Administrateur", "admin@cmtch.tn", "+21612345678", "ADMIN001", "1990-01-01", 1, 1, 0, None, 1))
            else:
                cur.execute("""
                    INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, is_admin, validated, is_trainer, email_verification_token, email_verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, ("admin", admin_password_hash, "Administrateur", "admin@cmtch.tn", "+21612345678", "ADMIN001", "1990-01-01", 1, 1, 0, None, 1))
            
            conn.commit()
            
            return {
                "status": "success",
                "message": "Utilisateur admin crÃ©Ã© avec succÃ¨s",
                "credentials": {
                    "username": "admin",
                    "password": "admin"
                }
            }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la correction: {str(e)}"
        }
    finally:
        conn.close()


@router.get("/restore-backup")
async def restore_backup_endpoint():
    """Point de terminaison pour forcer la restauration depuis une sauvegarde."""
    try:
        # Trouver la sauvegarde la plus rÃ©cente
        latest_backup = find_latest_backup()
        
        if not latest_backup:
            return {
                "status": "error",
                "message": "Aucune sauvegarde trouvÃ©e"
            }
        
        # Restaurer la base de donnÃ©es
        if restore_database(latest_backup):
            return {
                "status": "success",
                "message": f"Base de donnÃ©es restaurÃ©e depuis {latest_backup}"
            }
        else:
            return {
                "status": "error",
                "message": "Ã‰chec de la restauration"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la restauration: {str(e)}"
        }


@router.get("/test-espace")
async def test_espace_endpoint():
    """Point de terminaison pour tester la logique de /espace sans authentification."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Test de la requÃªte SQL
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        
        # Test de la requÃªte de rÃ©servations (pour l'utilisateur 1)
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur.execute(
                "SELECT substr(date, 1, 7) AS month, COUNT(*) AS count FROM reservations WHERE user_id = %s GROUP BY month ORDER BY month",
                (1,),
            )
        else:
            cur.execute(
                "SELECT substr(date, 1, 7) AS month, COUNT(*) AS count FROM reservations WHERE user_id = ? GROUP BY month ORDER BY month",
                (1,),
            )
        rows = cur.fetchall()
        
        conn.close()
        
        # Transformer les rÃ©sultats
        months = []
        counts = []
        for row in rows:
            months.append(row.month)
            counts.append(row.count)
        
        return {
            "status": "success",
            "users_count": users_count,
            "reservations_data": {
                "months": months,
                "counts": counts,
                "rows_count": len(rows)
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur dans le test /espace: {str(e)}"
        }


@router.get("/disable-auto-backup")
async def disable_auto_backup_endpoint():
    """Point de terminaison pour dÃ©sactiver le systÃ¨me de sauvegarde automatique."""
    try:
        # CrÃ©er un fichier de flag pour dÃ©sactiver la sauvegarde automatique
        flag_file = Path("DISABLE_AUTO_BACKUP")
        flag_file.touch()
        
        return {
            "status": "success",
            "message": "SystÃ¨me de sauvegarde automatique dÃ©sactivÃ©. RedÃ©marrez l'application pour appliquer."
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la dÃ©sactivation: {str(e)}"
        }


@router.get("/enable-auto-backup")
async def enable_auto_backup_endpoint():
    """Point de terminaison pour rÃ©activer le systÃ¨me de sauvegarde automatique."""
    try:
        # Supprimer le fichier de flag pour rÃ©activer la sauvegarde automatique
        flag_file = Path("DISABLE_AUTO_BACKUP")
        if flag_file.exists():
            flag_file.unlink()
        
        return {
            "status": "success",
            "message": "SystÃ¨me de sauvegarde automatique rÃ©activÃ©. RedÃ©marrez l'application pour appliquer."
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la rÃ©activation: {str(e)}"
        }







@router.get("/debug-table-structure")
async def debug_table_structure_endpoint():
    """Debug la structure de la table articles"""
    try:
        import sqlite3
        
        # Connexion Ã  la base de donnÃ©es
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # RÃ©cupÃ©rer la structure de la table articles
        cursor.execute("PRAGMA table_info(articles)")
        columns = cursor.fetchall()
        
        # RÃ©cupÃ©rer quelques exemples d'articles
        cursor.execute("SELECT * FROM articles LIMIT 3")
        sample_articles = cursor.fetchall()
        
        # RÃ©cupÃ©rer le total d'articles
        cursor.execute("SELECT COUNT(*) FROM articles")
        total_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "status": "success",
            "table_structure": {
                "columns": [
                    {
                        "id": col[0],
                        "name": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "default_value": col[4],
                        "primary_key": bool(col[5])
                    }
                    for col in columns
                ]
            },
            "total_articles": total_count,
            "sample_articles": sample_articles,
            "column_names": [col[1] for col in columns]
        }
        
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug-latest-articles")
async def debug_latest_articles_endpoint():
    """Debug la section 'Derniers articles'"""
    try:
        import sqlite3
        
        # Connexion Ã  la base de donnÃ©es
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # RÃ©cupÃ©rer tous les articles avec leurs dÃ©tails
        cursor.execute("""
            SELECT id, title, content, image_path, created_at 
            FROM articles 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        articles = cursor.fetchall()
        
        # RÃ©cupÃ©rer le total d'articles
        cursor.execute("SELECT COUNT(*) FROM articles")
        total_count = cursor.fetchone()[0]
        
        # Tous les articles sont considÃ©rÃ©s comme publiÃ©s (pas de colonne type)
        published_count = total_count
        
        conn.close()
        
        # Analyser chaque article
        analyzed_articles = []
        for article in articles:
            article_id, title, content, image_path, created_at = article
            
            # VÃ©rifier si l'image est accessible
            image_accessible = False
            if image_path:
                if image_path.startswith('https://www.cmtch.online/image/'):
                    image_accessible = True
                elif image_path.startswith('/static/article_images/'):
                    image_accessible = False
                else:
                    image_accessible = True
            
            analyzed_articles.append({
                "id": article_id,
                "title": title,
                "content_preview": content[:100] + "..." if content and len(content) > 100 else content,
                "image_path": image_path,
                "image_accessible": image_accessible,
                "created_at": created_at,
                "has_content": bool(content and content.strip()),
                "has_title": bool(title and title.strip())
            })
        
        return {
            "status": "success",
            "total_articles": total_count,
            "published_articles": published_count,
            "latest_articles": analyzed_articles,
            "diagnosis": {
                "articles_exist": total_count > 0,
                "published_exist": published_count > 0,
                "all_articles_have_content": all(a["has_content"] for a in analyzed_articles),
                "all_articles_have_title": all(a["has_title"] for a in analyzed_articles),
                "all_images_accessible": all(a["image_accessible"] for a in analyzed_articles)
            }
        }
        
    except Exception as e:
        return {"error": str(e)}

@router.get("/diagnose-database")
async def diagnose_database_endpoint():
    """Diagnostique la base de donnÃ©es"""
    try:
        import sqlite3
        import os
        
        # VÃ©rifier si le fichier de base existe
        db_files = []
        for db_file in ['cmtch.db', 'database.db', 'database.sqlite']:
            if os.path.exists(db_file):
                db_files.append(db_file)
        
        if not db_files:
            return {
                "error": "Aucun fichier de base de donnÃ©es trouvÃ©",
                "searched_files": ['cmtch.db', 'database.db', 'database.sqlite']
            }
        
        # Tester chaque base de donnÃ©es
        results = {}
        for db_file in db_files:
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                
                # Lister toutes les tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                
                # VÃ©rifier si la table articles existe
                has_articles = 'articles' in tables
                
                if has_articles:
                    # Compter les articles
                    cursor.execute("SELECT COUNT(*) FROM articles")
                    article_count = cursor.fetchone()[0]
                    
                    # RÃ©cupÃ©rer quelques exemples
                    cursor.execute("SELECT id, title, image_path FROM articles LIMIT 3")
                    sample_articles = cursor.fetchall()
                else:
                    article_count = 0
                    sample_articles = []
                
                conn.close()
                
                results[db_file] = {
                    "exists": True,
                    "tables": tables,
                    "has_articles_table": has_articles,
                    "article_count": article_count,
                    "sample_articles": sample_articles
                }
                
            except Exception as e:
                results[db_file] = {
                    "exists": True,
                    "error": str(e)
                }
        
        return {
            "status": "success",
            "database_files": db_files,
            "results": results
        }
        
    except Exception as e:
        return {"error": str(e)}

@router.get("/setup-imgbb")
async def setup_imgbb_endpoint():
    """Configuration et test d'ImgBB (service d'images gratuit)"""
    try:
        # Instructions pour obtenir une clÃ© API ImgBB
        instructions = {
            "step1": "Aller sur https://api.imgbb.com/",
            "step2": "Cliquer sur 'Get API Key'",
            "step3": "S'inscrire gratuitement (pas de carte de crÃ©dit)",
            "step4": "Copier la clÃ© API",
            "step5": "Remplacer 'YOUR_IMGBB_API_KEY' dans photo_upload_service_imgbb.py",
            "benefits": [
                "Gratuit et illimitÃ©",
                "32MB par image",
                "URLs permanentes",
                "Pas de blocage serveur",
                "Fiable et rapide"
            ]
        }
        
        return {
            "status": "success",
            "message": "Instructions pour configurer ImgBB",
            "instructions": instructions,
            "next_step": "Obtenir une clÃ© API ImgBB et la configurer"
        }
        
    except Exception as e:
        return {"error": str(e)}

@router.get("/test-db-connection")
async def test_db_connection_endpoint():
    """Test de la connexion Ã  la base de donnÃ©es"""
    try:
        from database import get_db_connection
        import os
        
        # Test de la connexion
        conn = get_db_connection()
        
        # VÃ©rifier le type de connexion
        connection_type = "unknown"
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            connection_type = "mysql"
        elif hasattr(conn, 'execute'):
            connection_type = "sqlite"
        elif hasattr(conn, 'cursor'):
            connection_type = "postgresql"
        
        # Test d'une requÃªte simple
        try:
            if connection_type == "mysql":
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) as count FROM articles")
                result = cur.fetchone()
                article_count = result[0] if result else 0
            else:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM articles")
                result = cur.fetchone()
                article_count = result[0] if result else 0
        except Exception as e:
            article_count = f"Erreur: {str(e)}"
        
        conn.close()
        
        return {
            "status": "success",
            "connection_type": connection_type,
            "database_url": os.getenv('DATABASE_URL', 'Non dÃ©fini'),
            "mysql_available": "mysql.connector" in str(type(conn)),
            "article_count": article_count,
            "connection_object": str(type(conn))
        }
        
    except Exception as e:
        return {"error": str(e)}

@router.get("/test-homepage-data")
async def test_homepage_data_endpoint():
    """Test des donnÃ©es de la page d'accueil"""
    try:
        from database import get_db_connection
        
        # RÃ©cupÃ©rer les donnÃ©es comme dans la route home
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
        
        # Analyser les donnÃ©es
        analyzed_articles = []
        for article in latest_articles:
            if hasattr(article, 'id'):
                # Objet avec attributs
                analyzed_articles.append({
                    "id": article.id,
                    "title": article.title,
                    "content": article.content,
                    "image_path": article.image_path,
                    "created_at": str(article.created_at),
                    "type": "object_with_attributes"
                })
            else:
                # Tuple
                analyzed_articles.append({
                    "id": article[0],
                    "title": article[1],
                    "content": article[2],
                    "image_path": article[3],
                    "created_at": str(article[4]),
                    "type": "tuple"
                })
        
        return {
            "status": "success",
            "total_articles": len(latest_articles),
            "articles": analyzed_articles,
            "connection_type": "mysql" if hasattr(conn, '_is_mysql') and conn._is_mysql else "sqlite"
        }
        
    except Exception as e:
        return {"error": str(e)}

@router.get("/test-imgbb")
async def test_imgbb_endpoint():
    """Test du systÃ¨me ImgBB"""
    try:
        return test_imgbb_system()
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur test ImgBB: {str(e)}",
            "imgbb_working": False
        }

@router.get("/force-update-all-image-urls")
async def force_update_all_image_urls_endpoint():
    """Force la mise Ã  jour de TOUTES les URLs d'images"""
    try:
        import sqlite3
        
        # Connexion Ã  la base de donnÃ©es
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # RÃ©cupÃ©rer tous les articles
        cursor.execute("SELECT id, image_path FROM articles")
        articles = cursor.fetchall()
        
        updated_count = 0
        
        for article_id, image_path in articles:
            if not image_path:
                continue
            
            # Extraire le nom du fichier
            if '/' in image_path:
                filename = image_path.split('/')[-1]
            else:
                filename = image_path
            
            # Nouvelle URL via notre endpoint
            new_url = f"https://www.cmtch.online/image/{filename}"
            
            # Mettre Ã  jour la base de donnÃ©es
            cursor.execute("UPDATE articles SET image_path = ? WHERE id = ?", (new_url, article_id))
            updated_count += 1
            
            print(f"âœ… Article {article_id}: {image_path} -> {new_url}")
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "message": f"{updated_count} articles mis Ã  jour avec les URLs d'images",
            "updated_count": updated_count,
            "new_base_url": "https://www.cmtch.online/image"
        }
        
    except Exception as e:
        return {"error": str(e)}








@router.get("/force-cache-refresh")
async def force_cache_refresh_endpoint():
    """Force le refresh du cache pour rÃ©soudre le problÃ¨me d'images"""
    try:
        # Vider le cache des templates
        templates.env.cache.clear()
        
        # Re-exposer la fonction pour s'assurer qu'elle est bien disponible
        templates.env.globals["ensure_absolute_image_url"] = ensure_absolute_image_url
        
        return {
            "status": "success",
            "message": "Cache vidÃ© et fonction re-exposÃ©e",
            "function_available": templates.env.globals.get('ensure_absolute_image_url') is not None
        }
        
    except Exception as e:
        return {"error": str(e)}

@router.get("/test-template-function")
async def test_template_function_endpoint():
    """Test simple pour vÃ©rifier que la fonction est accessible dans les templates"""
    try:
        # Test simple avec un template minimal
        test_template = """
        <html>
        <body>
            <h1>Test de la fonction ensure_absolute_image_url</h1>
            <p>URL test: {{ ensure_absolute_image_url('https://www.cmtch.online/static/article_images/test.jpg') }}</p>
            <p>URL relative: {{ ensure_absolute_image_url('/static/article_images/test.jpg') }}</p>
            <p>Nom fichier: {{ ensure_absolute_image_url('test.jpg') }}</p>
        </body>
        </html>
        """
        
        from jinja2 import Template
        template = Template(test_template)
        rendered = template.render(ensure_absolute_image_url=ensure_absolute_image_url)
        
        return HTMLResponse(content=rendered)
        
    except Exception as e:
        return {"error": str(e)}

@router.get("/test-html-generation")
async def test_html_generation_endpoint():
    """Test pour voir le HTML gÃ©nÃ©rÃ© avec les URLs d'images"""
    try:
        conn = get_db_connection()
        
        # RÃ©cupÃ©rer l'article 4
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            cur, column_names = execute_with_names("SELECT id, title, content, image_path, created_at FROM articles WHERE id = %s", (4,))
            article = cur.fetchone()
            if article:
                article = convert_mysql_result(article, column_names)
        else:
            cur = conn.cursor()
            cur.execute("SELECT id, title, content, image_path, created_at FROM articles WHERE id = ?", (4,))
            article = cur.fetchone()
        
        conn.close()
        
        if not article:
            return {"error": "Article 4 non trouvÃ©"}
        
        # Tester la fonction ensure_absolute_image_url
        original_url = article.image_path if hasattr(article, 'image_path') else article[3]
        absolute_url = ensure_absolute_image_url(original_url)
        
        # VÃ©rifier les attributs de l'article
        article_attrs = {}
        if hasattr(article, '__dict__'):
            article_attrs = article.__dict__
        elif hasattr(article, '_fields'):
            # Pour les tuples nommÃ©s
            article_attrs = {field: getattr(article, field) for field in article._fields}
        else:
            # Pour les tuples simples
            article_attrs = {
                'id': article[0] if len(article) > 0 else None,
                'title': article[1] if len(article) > 1 else None,
                'content': article[2] if len(article) > 2 else None,
                'image_path': article[3] if len(article) > 3 else None,
                'created_at': article[4] if len(article) > 4 else None
            }
        
        # GÃ©nÃ©rer le HTML pour voir ce qui est rÃ©ellement produit
        from fastapi import Request
        from fastapi.templating import Jinja2Templates
        
        # CrÃ©er une requÃªte factice pour le template
        class MockRequest:
            def __init__(self):
                self.url = "https://www.cmtch.online/articles/4"
        
        mock_request = MockRequest()
        
        # Rendre le template article_detail.html
        template_html = templates.get_template("article_detail.html")
        rendered_html = template_html.render(
            request=mock_request,
            article=article,
            user=None,
            article_url="https://www.cmtch.online/articles/4"
        )
        
        # Extraire la balise img du HTML gÃ©nÃ©rÃ© (spÃ©cifiquement l'image de l'article)
        import re
        # Chercher l'image avec la classe "article-featured-image"
        img_match = re.search(r'<img[^>]*class="[^"]*article-featured-image[^"]*"[^>]*src="([^"]*)"[^>]*>', rendered_html)
        if not img_match:
            # Si pas trouvÃ©, chercher dans la div "article-image-container"
            img_match = re.search(r'<div[^>]*class="[^"]*article-image-container[^"]*"[^>]*>.*?<img[^>]*src="([^"]*)"[^>]*>', rendered_html, re.DOTALL)
        if not img_match:
            # Si toujours pas trouvÃ©, chercher n'importe quelle image
            img_match = re.search(r'<img[^>]*src="([^"]*)"[^>]*>', rendered_html)
        
        img_src_in_html = img_match.group(1) if img_match else "Non trouvÃ©"
        
        return {
            "article_id": article.id if hasattr(article, 'id') else article[0],
            "title": article.title if hasattr(article, 'title') else article[1],
            "original_image_path": original_url,
            "absolute_image_url": absolute_url,
            "function_works": original_url != absolute_url or original_url.startswith('https://'),
            "img_src_in_html": img_src_in_html,
            "html_contains_absolute_url": "https://www.cmtch.online" in img_src_in_html,
            "article_attrs": article_attrs,
            "image_path_in_template": article.image_path if hasattr(article, 'image_path') else article[3],
            "image_path_is_truthy": bool(article.image_path if hasattr(article, 'image_path') else article[3])
        }
        
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug-article-images")
async def debug_article_images_endpoint():
    """Endpoint pour dÃ©boguer les images d'articles"""
    try:
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            
            # RÃ©cupÃ©rer tous les articles
            cur, column_names = execute_with_names("SELECT id, title, image_path FROM articles")
            articles = cur.fetchall()
            # Convertir les tuples MySQL en objets avec attributs nommÃ©s
            articles = [convert_mysql_result(article, column_names) for article in articles]
        else:
            cur = conn.cursor()
            cur.execute("SELECT id, title, image_path FROM articles")
            articles = cur.fetchall()
        
        conn.close()
        
        debug_info = []
        for article in articles:
            if hasattr(article, 'id'):
                # MySQL
                article_id = article.id
                title = article.title
                image_path = article.image_path
            else:
                # SQLite
                article_id, title, image_path = article
            
            debug_info.append({
                "id": article_id,
                "title": title,
                "image_path": image_path,
                "image_path_type": type(image_path).__name__,
                "image_path_length": len(str(image_path)) if image_path else 0,
                "is_hostgator_url": str(image_path).startswith('https://www.cmtch.online') if image_path else False
            })
        
        return {
            "status": "success",
            "message": f"Debug info pour {len(debug_info)} articles",
            "articles": debug_info
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors du debug: {str(e)}"
        }

@router.get("/fix-production-images")
async def fix_production_images_endpoint():
    """Endpoint pour corriger les images en production"""
    try:
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            
            # RÃ©cupÃ©rer tous les articles
            cur, column_names = execute_with_names("SELECT id, title, image_path FROM articles")
            articles = cur.fetchall()
            # Convertir les tuples MySQL en objets avec attributs nommÃ©s
            articles = [convert_mysql_result(article, column_names) for article in articles]
            
            fixed_count = 0
            
            for article in articles:
                article_id = article.id
                title = article.title
                image_path = article.image_path
                
                # VÃ©rifier si l'image est manquante ou invalide
                needs_fix = False
                
                if not image_path or image_path == '':
                    needs_fix = True
                elif not image_path.startswith('https://www.cmtch.online'):
                    needs_fix = True
                elif 'article_images' in image_path and not image_path.endswith('default_article.jpg'):
                    needs_fix = True
                
                if needs_fix:
                    # Utiliser l'image par dÃ©faut HostGator
                    default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
                    
                    cur.execute("UPDATE articles SET image_path = %s WHERE id = %s", (default_url, article_id))
                    conn.commit()
                    fixed_count += 1
        else:
            # SQLite
            cur = conn.cursor()
            
            # RÃ©cupÃ©rer tous les articles
            cur.execute("SELECT id, title, image_path FROM articles")
            articles = cur.fetchall()
            
            fixed_count = 0
            
            for article_id, title, image_path in articles:
                # VÃ©rifier si l'image est manquante ou invalide
                needs_fix = False
                
                if not image_path or image_path == '':
                    needs_fix = True
                elif not image_path.startswith('https://www.cmtch.online'):
                    needs_fix = True
                elif 'article_images' in image_path and not image_path.endswith('default_article.jpg'):
                    needs_fix = True
                
                if needs_fix:
                    # Utiliser l'image par dÃ©faut HostGator
                    default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
                    
                    cur.execute("UPDATE articles SET image_path = ? WHERE id = ?", (default_url, article_id))
                    conn.commit()
                    fixed_count += 1
        
        conn.close()
        
        return {
            "status": "success",
            "message": f"Correction terminÃ©e: {fixed_count} articles corrigÃ©s sur {len(articles)}",
            "fixed_count": fixed_count,
            "total_articles": len(articles)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la correction: {str(e)}"
        }

@router.get("/force-disable-backup")
async def force_disable_backup_endpoint():
    """Point de terminaison pour forcer la dÃ©sactivation du systÃ¨me de sauvegarde."""
    try:
        # CrÃ©er le fichier de flag
        flag_file = Path("DISABLE_AUTO_BACKUP")
        flag_file.touch()
        
        # VÃ©rifier l'Ã©tat actuel de la base
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM articles")
        articles_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM reservations")
        reservations_count = cur.fetchone()[0]
        
        conn.close()
        
        return {
            "status": "success",
            "message": "SystÃ¨me de sauvegarde FORCÃ‰MENT dÃ©sactivÃ©",
            "current_data": {
                "users": users_count,
                "articles": articles_count,
                "reservations": reservations_count
            },
            "note": "Vos donnÃ©es actuelles sont prÃ©servÃ©es. Le systÃ¨me ne touchera plus Ã  votre base."
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la dÃ©sactivation forcÃ©e: {str(e)}"
        }


@router.get("/check-backup-status")
async def check_backup_status_endpoint():
    """Point de terminaison pour vÃ©rifier l'Ã©tat du systÃ¨me de sauvegarde."""
    try:
        flag_file = Path("DISABLE_AUTO_BACKUP")
        is_disabled = flag_file.exists()
        
        # VÃ©rifier l'Ã©tat de la base
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM articles")
        articles_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM reservations")
        reservations_count = cur.fetchone()[0]
        
        conn.close()
        
        return {
            "status": "success",
            "backup_system": {
                "disabled": is_disabled,
                "auto_backup_disabled": True,  # DÃ©sactivÃ© par dÃ©faut maintenant
                "manual_control": True
            },
            "database": {
                "users": users_count,
                "articles": articles_count,
                "reservations": reservations_count,
                "has_data": users_count > 0 or articles_count > 0 or reservations_count > 0
            },
            "recommendation": "SystÃ¨me dÃ©sactivÃ© - vos donnÃ©es sont protÃ©gÃ©es"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la vÃ©rification: {str(e)}"
        }



@router.get("/create-admin")
async def create_admin_endpoint():
    """Point de terminaison pour crÃ©er l'utilisateur admin si la base est vide."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # VÃ©rifier si la base contient des donnÃ©es
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        
        if users_count > 0:
            return {
                "status": "info",
                "message": f"La base contient dÃ©jÃ  {users_count} utilisateur(s). Utilisez /fix-admin pour corriger l'admin.",
                "users_count": users_count
            }
        
        # CrÃ©er l'utilisateur admin si la base est vide
        admin_password = "admin"
        admin_password_hash = hash_password(admin_password)
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, is_admin, validated, is_trainer, email_verification_token, email_verified)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, ("admin", admin_password_hash, "Administrateur", "admin@cmtch.tn", "+21612345678", "ADMIN001", "1990-01-01", 1, 1, 0, None, 1))
        else:
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, is_admin, validated, is_trainer, email_verification_token, email_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("admin", admin_password_hash, "Administrateur", "admin@cmtch.tn", "+21612345678", "ADMIN001", "1990-01-01", 1, 1, 0, None, 1))
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "message": "Base de donnÃ©es vide - Utilisateur admin crÃ©Ã© avec succÃ¨s",
            "note": "Connectez-vous avec le compte admin puis changez immÃ©diatement le mot de passe.",
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la crÃ©ation: {str(e)}"
        }

@router.get("/backup-database")
async def backup_database_endpoint(request: Request):
    """Endpoint pour crÃ©er une sauvegarde de la base de donnÃ©es."""
    try:
        user = get_current_user(request)
        
        if not user or not user.is_admin:
            return {
                "status": "error",
                "message": "AccÃ¨s refusÃ© - droits administrateur requis"
            }
        
        # Utiliser la fonction de sauvegarde existante
        result = backup_database()
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la sauvegarde: {str(e)}"
        }

@router.get("/list-backups")
async def list_backups_endpoint(request: Request):
    """Endpoint pour lister les sauvegardes disponibles."""
    try:
        user = get_current_user(request)
        
        if not user or not user.is_admin:
            return {
                "status": "error",
                "message": "AccÃ¨s refusÃ© - droits administrateur requis"
            }
        
        # Lister les sauvegardes disponibles
        backup_dir = Path("backups")
        if not backup_dir.exists():
            return {
                "status": "success",
                "message": "Aucune sauvegarde trouvÃ©e",
                "backups": []
            }
        
        backup_files = []
        for file_path in backup_dir.glob("backup_*"):
            backup_files.append({
                "filename": file_path.name,
                "path": str(file_path),
                "size": file_path.stat().st_size,
                "modified": file_path.stat().st_mtime
            })
        
        result = {
            "status": "success",
            "message": f"{len(backup_files)} sauvegarde(s) trouvÃ©e(s)",
            "backups": backup_files
        }
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la liste des sauvegardes: {str(e)}"
        }

@router.get("/test-admin-reservations")
async def test_admin_reservations(request: Request):
    """Endpoint de test pour diagnostiquer le problÃ¨me des rÃ©servations admin"""
    try:
        user = get_current_user(request)
        
        if not user:
            return {
                "status": "error",
                "message": "Utilisateur non connectÃ©",
                "step": "authentication"
            }
        
        if not user.is_admin:
            return {
                "status": "error", 
                "message": "Utilisateur non administrateur",
                "step": "admin_check",
                "user_info": {
                    "username": user.username,
                    "is_admin": bool(user.is_admin),
                    "validated": bool(user.validated)
                }
            }
        
        # Test de connexion Ã  la base de donnÃ©es
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Test de la table reservations
            cur.execute("SELECT COUNT(*) FROM reservations")
            reservations_count = cur.fetchone()[0]
            
            # Test de la table users
            cur.execute("SELECT COUNT(*) FROM users")
            users_count = cur.fetchone()[0]
            
            conn.close()
            
            return {
                "status": "success",
                "message": "Tous les tests passent",
                "user": {
                    "username": user.username,
                    "is_admin": bool(user.is_admin),
                    "validated": bool(user.validated)
                },
                "database": {
                    "reservations_count": reservations_count,
                    "users_count": users_count
                }
            }
            
        except Exception as db_error:
            return {
                "status": "error",
                "message": f"Erreur de base de donnÃ©es: {str(db_error)}",
                "step": "database_connection",
                "user_info": {
                    "username": user.username,
                    "is_admin": bool(user.is_admin)
                }
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur gÃ©nÃ©rale: {str(e)}",
            "step": "general"
        }
