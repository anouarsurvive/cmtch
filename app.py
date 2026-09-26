"""
Application web pour le Club municipal de tennis Chihia.

Ce module dÃ©finit une application FastAPI simple qui fournit un site web en
langue franÃ§aise pour le club de tennis de Chihia.  Le site comporte un
espace public prÃ©sentant le club, un formulaire d'inscription pour les
nouveaux membres, un systÃ¨me d'authentification, un espace d'administration
permettant de valider les inscriptions et de gÃ©rer les membres, ainsi qu'un
module de rÃ©servation pour les trois courts du club.

Pour simplifier le dÃ©ploiement dans cet environnement, aucune dÃ©pendance
externe n'est requise : FastAPI, Starlette et Jinja2 sont dÃ©jÃ  fournis.
La base de donnÃ©es utilise SQLite via le module standard `sqlite3`.  Les
sessions sont gÃ©rÃ©es via le middleware de Starlette qui signe un cookie
contant un identifiant d'utilisateur.

Les mots de passe sont hachÃ©s avec bcrypt (migration automatique depuis SHA-256).
Les endpoints de diagnostic / ops sont dÃ©sactivÃ©s par dÃ©faut
(ENABLE_OPS_ENDPOINTS + SETUP_TOKEN).

Autor: ChatGPT / CMTCH
"""

from __future__ import annotations

import hashlib
import os
import sys
import sqlite3
from datetime import datetime, date, time, timedelta
import secrets
import json

# Import du service de stockage d'images ImgBB
# Ajouter le rÃ©pertoire courant au path pour s'assurer que l'import fonctionne
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from photo_upload_service_imgbb import upload_photo_to_imgbb, test_imgbb_system  # type: ignore
except ImportError as e:
    # Si l'import Ã©choue, crÃ©er des fonctions de fallback
    print(f"Attention: Impossible d'importer photo_upload_service_imgbb: {e}")
    def upload_photo_to_imgbb(file_data: bytes, filename: str) -> Dict[str, Any]:
        return {'success': False, 'error': 'Service d\'upload d\'images non disponible'}
    def test_imgbb_system() -> Dict[str, Any]:
        return {'status': 'error', 'message': 'Service d\'upload d\'images non disponible', 'imgbb_working': False}

from security_utils import (
    SECRET_KEY,
    COOKIE_SECURE,
    UNSAFE_METHODS,
    CSRF_EXEMPT_PREFIXES,
    generate_csrf_token,
    csrf_tokens_match,
    is_ops_path,
    ops_access_allowed,
    session_cookie_kwargs,
    hash_password as secure_hash_password,
    verify_password as secure_verify_password,
    needs_rehash as secure_needs_rehash,
)

from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import urllib.parse
from fastapi.templating import Jinja2Templates
import base64
import hmac
import re
import uuid
from io import BytesIO
import json


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

app = FastAPI()


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Bloque les endpoints ops, valide le CSRF, gÃ¨re le cookie CSRF."""
    path = request.url.path

    # Endpoints de diagnostic / setup : dÃ©sactivÃ©s sans token
    if is_ops_path(path):
        setup_token = request.query_params.get("token") or request.headers.get(
            "X-Setup-Token"
        )
        if not ops_access_allowed(setup_token):
            return JSONResponse({"detail": "Not Found"}, status_code=404)

    # Protection CSRF sur les mÃ©thodes mutantes
    if request.method.upper() in UNSAFE_METHODS and not any(
        path.startswith(p) for p in CSRF_EXEMPT_PREFIXES
    ):
        cookie_token = request.cookies.get("csrf_token")
        submitted = request.headers.get("X-CSRF-Token")

        # Relire le body une seule fois puis le rejouer (Ã©vite de casser uploads)
        if not submitted:
            body = await request.body()

            async def _receive():
                return {"type": "http.request", "body": body, "more_body": False}

            request = Request(request.scope, _receive)

            content_type = request.headers.get("content-type", "")
            if "application/x-www-form-urlencoded" in content_type:
                try:
                    from urllib.parse import parse_qs
                    parsed = parse_qs(body.decode("utf-8", errors="ignore"))
                    vals = parsed.get("csrf_token") or []
                    submitted = vals[0] if vals else None
                except Exception:
                    submitted = None
            elif "multipart/form-data" in content_type:
                # Extraire csrf_token sans parser tout le multipart fichier
                try:
                    marker = b'name="csrf_token"'
                    idx = body.find(marker)
                    if idx != -1:
                        after = body[idx + len(marker) :]
                        # sauter jusqu'aux donnÃ©es (aprÃ¨s headers de part)
                        sep = after.find(b"\r\n\r\n")
                        if sep != -1:
                            data = after[sep + 4 :]
                            end = data.find(b"\r\n")
                            submitted = data[:end].decode("utf-8", errors="ignore").strip()
                except Exception:
                    submitted = None

        if not csrf_tokens_match(cookie_token, submitted if isinstance(submitted, str) else None):
            accept = request.headers.get("accept", "")
            if "text/html" in accept:
                return HTMLResponse(
                    "<h1>403 â€” Jeton CSRF invalide</h1><p>Rechargez la page et rÃ©essayez.</p>",
                    status_code=403,
                )
            return JSONResponse(
                {"detail": "Jeton CSRF invalide ou manquant"}, status_code=403
            )

    # Token CSRF pour la requÃªte / templates
    csrf = request.cookies.get("csrf_token") or generate_csrf_token()
    request.state.csrf_token = csrf

    response = await call_next(request)

    if "csrf_token" not in request.cookies:
        response.set_cookie(
            key="csrf_token",
            value=csrf,
            httponly=False,
            max_age=60 * 60 * 24 * 7,
            secure=COOKIE_SECURE,
            samesite="lax",
            path="/",
        )
    return response


# Middleware pour la gestion des sessions sÃ©curisÃ©es
@app.middleware("http")
async def session_middleware(request: Request, call_next):
    """Middleware pour gÃ©rer les sessions sÃ©curisÃ©es et la rÃ©gÃ©nÃ©ration des tokens."""
    response = await call_next(request)
    
    # VÃ©rifier si l'utilisateur est connectÃ©
    token = request.cookies.get("session_token")
    if token:
        # VÃ©rifier si le token doit Ãªtre rafraÃ®chi
        if should_refresh_token(token):
            try:
                # RÃ©cupÃ©rer l'utilisateur actuel
                user_id = validate_session_token(token)
                if user_id:
                    # CrÃ©er un nouveau token
                    ip_address = request.client.host if request.client else None
                    user_agent = request.headers.get("user-agent")
                    new_token = create_secure_session_token(user_id, ip_address, user_agent)
                    
                    # DÃ©sactiver l'ancien token
                    deactivate_session(token)
                    
                    # Mettre Ã  jour le cookie
                    response.set_cookie(
                        key="session_token",
                        value=new_token,
                        **session_cookie_kwargs(60 * 60 * 24 * SESSION_MAX_AGE_DAYS),
                    )
            except Exception as e:
                print(f"Erreur lors de la rÃ©gÃ©nÃ©ration du token : {e}")
    
    return response

# Configuration des sessions sÃ©curisÃ©es
SESSION_TIMEOUT_MINUTES = 30  # Timeout d'inactivitÃ©
SESSION_MAX_AGE_DAYS = 7      # DurÃ©e maximale de la session
SESSION_REFRESH_THRESHOLD = 15 # Minutes avant expiration pour rÃ©gÃ©nÃ©rer le token

# Configuration email
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@cmtch.tn")

def detect_language(text: str) -> str:
    """
    DÃ©tecte la langue d'un texte (arabe ou franÃ§ais)
    Retourne 'ar' pour l'arabe, 'fr' pour le franÃ§ais
    """
    if not text or not text.strip():
        return 'fr'  # Par dÃ©faut franÃ§ais
    
    # Compter les caractÃ¨res arabes
    arabic_chars = re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', text)
    arabic_count = len(arabic_chars)
    
    # Compter les caractÃ¨res franÃ§ais/latins
    latin_chars = re.findall(r'[a-zA-ZÃ Ã¢Ã¤Ã©Ã¨ÃªÃ«Ã¯Ã®Ã´Ã¶Ã¹Ã»Ã¼Ã¿Ã§Ã±]', text)
    latin_count = len(latin_chars)
    
    # Si plus de caractÃ¨res arabes que latins, c'est de l'arabe
    if arabic_count > latin_count:
        return 'ar'
    else:
        return 'fr'

def get_text_direction(language: str) -> str:
    """
    Retourne la direction du texte selon la langue
    """
    return 'rtl' if language == 'ar' else 'ltr'

def get_text_align(language: str) -> str:
    """
    Retourne l'alignement du texte selon la langue
    """
    return 'right' if language == 'ar' else 'left'

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
# Expose l'objet datetime dans les templates pour afficher l'annÃ©e dans le pied de page
templates.env.globals["datetime"] = datetime
# Expose les fonctions de dÃ©tection de langue dans les templates
templates.env.globals["detect_language"] = detect_language
templates.env.globals["get_text_direction"] = get_text_direction
templates.env.globals["get_text_align"] = get_text_align

_original_template_response = templates.TemplateResponse

def _template_response_with_csrf(name, context, *args, **kwargs):
    """Injecte automatiquement csrf_token dans le contexte Jinja."""
    request = context.get("request") if isinstance(context, dict) else None
    if isinstance(context, dict) and request is not None:
        context.setdefault(
            "csrf_token",
            getattr(request.state, "csrf_token", None) or request.cookies.get("csrf_token") or "",
        )
    return _original_template_response(name, context, *args, **kwargs)

templates.TemplateResponse = _template_response_with_csrf  # type: ignore[method-assign]

def ensure_absolute_image_url(image_path: str) -> str:
    """S'assure que l'URL de l'image est absolue (ImgBB ou endpoint)"""
    if not image_path:
        return ""
    
    print(f"ðŸ” ensure_absolute_image_url: Input = '{image_path}'")
    
    # Si c'est dÃ©jÃ  une URL absolue, la retourner telle quelle
    if image_path.startswith(('http://', 'https://')):
        print(f"âœ… URL dÃ©jÃ  absolue: {image_path}")
        return image_path
    
    # Si c'est une URL relative, la convertir en URL absolue via notre endpoint
    if image_path.startswith('/static/article_images/'):
        filename = image_path.split('/')[-1]
        result = f"https://www.cmtch.online/image/{filename}"
        print(f"ðŸ”„ URL relative convertie: {image_path} -> {result}")
        return result
    
    # Si c'est juste le nom du fichier, construire l'URL via notre endpoint
    if not image_path.startswith('/'):
        result = f"https://www.cmtch.online/image/{image_path}"
        print(f"ðŸ”„ Nom de fichier converti: {image_path} -> {result}")
        return result
    
    # Par dÃ©faut, retourner l'URL telle quelle
    print(f"âš ï¸ URL non modifiÃ©e: {image_path}")
    return image_path

# Expose la fonction dans les templates
templates.env.globals["ensure_absolute_image_url"] = ensure_absolute_image_url

# Test pour vÃ©rifier que la fonction est bien exposÃ©e
print(f"ðŸ”§ Fonction ensure_absolute_image_url exposÃ©e: {templates.env.globals.get('ensure_absolute_image_url') is not None}")

# Montage des fichiers statiques (CSS, images, JS)
# Montage StaticFiles pour les fichiers CSS/JS locaux
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)

# Route spÃ©cifique pour les images d'articles qui redirige vers HostGator
@app.get("/article_images/{filename}")
async def serve_article_image(filename: str):
    """Redirige les requÃªtes d'images d'articles vers HostGator"""
    hostgator_url = f"https://www.cmtch.online/static/article_images/{filename}"
    return RedirectResponse(url=hostgator_url, status_code=302)


def create_secure_session_token(user_id: int, ip_address: str = None, user_agent: str = None) -> str:
    """CrÃ©e un jeton de session sÃ©curisÃ© et l'enregistre en base de donnÃ©es.

    Args:
        user_id: identifiant numÃ©rique de l'utilisateur.
        ip_address: adresse IP de l'utilisateur.
        user_agent: user agent du navigateur.

    Returns:
        ChaÃ®ne reprÃ©sentant le jeton de session.
    """
    # GÃ©nÃ©rer un token alÃ©atoire sÃ©curisÃ©
    token = secrets.token_urlsafe(32)
    
    # Calculer les dates d'expiration
    now = datetime.now()
    expires_at = now + timedelta(days=SESSION_MAX_AGE_DAYS)
    
    # Enregistrer la session en base de donnÃ©es
    conn = get_db_connection()
    try:
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO user_sessions (user_id, session_token, expires_at, last_activity, ip_address, user_agent)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, token, expires_at.isoformat(), now.isoformat(), ip_address, user_agent))
        else:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO user_sessions (user_id, session_token, expires_at, last_activity, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, token, expires_at.isoformat(), now.isoformat(), ip_address, user_agent))
        
        conn.commit()
        return token
    except Exception as e:
        # Si la table user_sessions n'existe pas encore, utiliser l'ancien systÃ¨me
        print(f"âš ï¸ Table user_sessions manquante, utilisation de l'ancien systÃ¨me: {e}")
        # Retourner un token simple pour l'ancien systÃ¨me
        data = str(user_id).encode()
        signature = hmac.new(SECRET_KEY.encode(), data, hashlib.sha256).hexdigest().encode()
        token_bytes = data + b":" + signature
        return base64.urlsafe_b64encode(token_bytes).decode()
    finally:
        conn.close()


def validate_session_token(token: str, ip_address: str = None) -> Optional[int]:
    """Valide un jeton de session et retourne l'ID utilisateur si valide.

    Args:
        token: Jeton de session Ã  valider.
        ip_address: Adresse IP pour vÃ©rification de sÃ©curitÃ©.

    Returns:
        L'identifiant de l'utilisateur si la session est valide, sinon None.
    """
    if not token:
        return None
    
    conn = get_db_connection()
    try:
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            cur.execute("""
                SELECT user_id, expires_at, last_activity, is_active, ip_address
                FROM user_sessions 
                WHERE session_token = %s AND is_active = 1
            """, (token,))
        else:
            cur = conn.cursor()
            cur.execute("""
                SELECT user_id, expires_at, last_activity, is_active, ip_address
                FROM user_sessions 
                WHERE session_token = ? AND is_active = 1
            """, (token,))
        
        session = cur.fetchone()
        if not session:
            return None
        
        user_id, expires_at_str, last_activity_str, is_active, session_ip = session
        
        # VÃ©rifier si la session est expirÃ©e
        try:
            expires_at = datetime.fromisoformat(str(expires_at_str)) if expires_at_str else datetime.now()
            last_activity = datetime.fromisoformat(str(last_activity_str)) if last_activity_str else datetime.now()
        except (ValueError, TypeError) as e:
            print(f"âš ï¸ Erreur de parsing de date: {e}")
            return None
        now = datetime.now()
        
        if now > expires_at:
            # Session expirÃ©e, la dÃ©sactiver
            deactivate_session(token)
            return None
        
        # VÃ©rifier le timeout d'inactivitÃ©
        if now - last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            # Session inactive trop longtemps, la dÃ©sactiver
            deactivate_session(token)
            return None
        
        # VÃ©rification optionnelle de l'IP (peut Ãªtre dÃ©sactivÃ©e pour plus de flexibilitÃ©)
        # if ip_address and session_ip and ip_address != session_ip:
        #     return None
        
        # Mettre Ã  jour la derniÃ¨re activitÃ©
        update_session_activity(token)
        
        return user_id
        
    except Exception as e:
        # Si la table user_sessions n'existe pas encore, utiliser l'ancien systÃ¨me
        print(f"âš ï¸ Table user_sessions manquante, utilisation de l'ancien systÃ¨me: {e}")
        return None
    finally:
        conn.close()


def update_session_activity(token: str) -> None:
    """Met Ã  jour la derniÃ¨re activitÃ© d'une session."""
    conn = get_db_connection()
    try:
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            cur.execute("""
                UPDATE user_sessions 
                SET last_activity = %s 
                WHERE session_token = %s
            """, (datetime.now().isoformat(), token))
        else:
            cur = conn.cursor()
            cur.execute("""
                UPDATE user_sessions 
                SET last_activity = ? 
                WHERE session_token = ?
            """, (datetime.now().isoformat(), token))
        
        conn.commit()
    finally:
        conn.close()


def deactivate_session(token: str) -> None:
    """DÃ©sactive une session."""
    conn = get_db_connection()
    try:
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            cur.execute("""
                UPDATE user_sessions 
                SET is_active = 0 
                WHERE session_token = %s
            """, (token,))
        else:
            cur = conn.cursor()
            cur.execute("""
                UPDATE user_sessions 
                SET is_active = 0 
                WHERE session_token = ?
            """, (token,))
        
        conn.commit()
    finally:
        conn.close()


def cleanup_expired_sessions() -> None:
    """Nettoie les sessions expirÃ©es."""
    conn = get_db_connection()
    try:
        now = datetime.now().isoformat()
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            cur.execute("""
                UPDATE user_sessions 
                SET is_active = 0 
                WHERE expires_at < %s OR last_activity < %s
            """, (now, (datetime.now() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)).isoformat()))
        else:
            cur = conn.cursor()
            cur.execute("""
                UPDATE user_sessions 
                SET is_active = 0 
                WHERE expires_at < ? OR last_activity < ?
            """, (now, (datetime.now() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)).isoformat()))
        
        conn.commit()
    finally:
        conn.close()


def should_refresh_token(token: str) -> bool:
    """VÃ©rifie si un token doit Ãªtre rafraÃ®chi."""
    conn = get_db_connection()
    try:
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            cur.execute("""
                SELECT expires_at FROM user_sessions 
                WHERE session_token = %s AND is_active = 1
            """, (token,))
        else:
            cur = conn.cursor()
            cur.execute("""
                SELECT expires_at FROM user_sessions 
                WHERE session_token = ? AND is_active = 1
            """, (token,))
        
        result = cur.fetchone()
        if not result:
            return False
        
        try:
            expires_at = datetime.fromisoformat(str(result[0])) if result[0] else datetime.now()
            refresh_threshold = datetime.now() + timedelta(minutes=SESSION_REFRESH_THRESHOLD)
            
            return datetime.now() < refresh_threshold < expires_at
        except (ValueError, TypeError) as e:
            print(f"âš ï¸ Erreur de parsing de date dans should_refresh_token: {e}")
            return False
        
    except Exception as e:
        # Si la table n'existe pas encore, ne pas rafraÃ®chir
        print(f"âš ï¸ Erreur lors de la vÃ©rification du token (table user_sessions manquante?): {e}")
        return False
    finally:
        conn.close()


# Fonctions de compatibilitÃ© avec l'ancien systÃ¨me
def create_session_token(user_id: int) -> str:
    """Fonction de compatibilitÃ© - utilise le nouveau systÃ¨me sÃ©curisÃ©."""
    try:
        return create_secure_session_token(user_id)
    except Exception as e:
        # Si le nouveau systÃ¨me Ã©choue, utiliser l'ancien systÃ¨me
        print(f"âš ï¸ Nouveau systÃ¨me de sessions indisponible, utilisation de l'ancien: {e}")
        data = str(user_id).encode()
        signature = hmac.new(SECRET_KEY.encode(), data, hashlib.sha256).hexdigest().encode()
        token_bytes = data + b":" + signature
        return base64.urlsafe_b64encode(token_bytes).decode()


def parse_session_token(token: Optional[str]) -> Optional[int]:
    """Fonction de compatibilitÃ© - utilise le nouveau systÃ¨me sÃ©curisÃ©."""
    if not token:
        return None
    
    # Essayer d'abord l'ancien systÃ¨me (plus fiable pour le fallback)
    try:
        token_bytes = base64.urlsafe_b64decode(token.encode())
        user_id_bytes, signature = token_bytes.split(b":", 1)
        expected_signature = hmac.new(SECRET_KEY.encode(), user_id_bytes, hashlib.sha256).hexdigest().encode()
        if hmac.compare_digest(signature, expected_signature):
            return int(user_id_bytes.decode())
    except Exception:
        pass
    
    # Si l'ancien systÃ¨me Ã©choue, essayer le nouveau systÃ¨me
    user_id = validate_session_token(token)
    if user_id is not None:
        return user_id
    
    return None





def verify_password(password: str, password_hash: str) -> bool:
    """VÃ©rifie qu'un mot de passe correspond Ã  une empreinte (bcrypt ou SHA-256 legacy)."""
    return secure_verify_password(password, password_hash)


# Utilitaire pour analyser les formulaires multipart/form-data sans dÃ©pendance
def parse_multipart_form(body: bytes, content_type: str) -> Dict[str, Any]:
    """Parse un corps multipart/form-data et retourne un dict des champs.

    Cette fonction analyse les donnÃ©es envoyÃ©es dans le corps d'une requÃªte
    multipart/form-data. Les champs simples (texte) sont retournÃ©s comme des
    chaÃ®nes de caractÃ¨res. Les champs de fichier sont retournÃ©s sous la forme
    d'un dictionnaire avec les clÃ©s 'filename' et 'content' (contenu binaire).

    Args:
        body: corps brut de la requÃªte en bytes.
        content_type: valeur de l'en-tÃªte Content-Type (avec le boundary).

    Returns:
        Un dictionnaire oÃ¹ les clÃ©s sont les noms de champs.
    """
    result: Dict[str, Any] = {}
    # Extraire le boundary depuis le header
    m = re.search(r"boundary=([^;]+)", content_type)
    if not m:
        return result
    boundary = m.group(1)
    # Les guillemets autour du boundary sont supprimÃ©s le cas Ã©chÃ©ant
    if boundary.startswith('"') and boundary.endswith('"'):
        boundary = boundary[1:-1]
    boundary_bytes = ('--' + boundary).encode()
    parts = body.split(boundary_bytes)
    # On ignore la premiÃ¨re et la derniÃ¨re partie (avant le premier boundary et aprÃ¨s le boundary de fermeture)
    for part in parts[1:-1]:
        part = part.strip(b"\r\n")
        if not part:
            continue
        # SÃ©parer les entÃªtes du contenu
        header_block, _, data = part.partition(b"\r\n\r\n")
        headers: Dict[str, str] = {}
        for header_line in header_block.split(b"\r\n"):
            try:
                key, _, value = header_line.decode(errors="replace").partition(":")
                headers[key.strip().lower()] = value.strip()
            except Exception:
                continue
        content_disp = headers.get('content-disposition', '')
        # Extraire les paramÃ¨tres du Content-Disposition
        disp_params = dict(re.findall(r'([^;=\s]+)="?([^";]*)"?', content_disp))
        field_name = disp_params.get('name')
        filename = disp_params.get('filename')
        # Nettoyer le contenu (supprimer le CRLF final)
        cleaned = data.rstrip(b"\r\n")
        if filename:
            result[field_name] = {"filename": filename, "content": cleaned}
        else:
            try:
                result[field_name] = cleaned.decode(errors="replace")
            except Exception:
                result[field_name] = ''
    return result


def get_db_connection():
    """Ouvre une connexion Ã  la base de donnÃ©es (SQLite ou PostgreSQL).

    Returns:
        Instance de connexion Ã  la base de donnÃ©es.
    """
    from database import get_db_connection as get_db_conn
    return get_db_conn()

def send_email(to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
    """Envoie un email via SMTP.
    
    Args:
        to_email: Adresse email du destinataire
        subject: Sujet de l'email
        html_content: Contenu HTML de l'email
        text_content: Contenu texte alternatif (optionnel)
        
    Returns:
        True si l'email a Ã©tÃ© envoyÃ© avec succÃ¨s, False sinon
    """
    try:
        if not SMTP_USERNAME or not SMTP_PASSWORD:
            print(f"âš ï¸ Configuration SMTP manquante - Email non envoyÃ© Ã  {to_email}")
            return False
            
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Ajouter le contenu texte et HTML
        if text_content:
            msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        # Connexion au serveur SMTP
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        
        # Envoi de l'email
        text = msg.as_string()
        server.sendmail(EMAIL_FROM, to_email, text)
        server.quit()
        
        print(f"âœ… Email envoyÃ© avec succÃ¨s Ã  {to_email}")
        return True
        
    except Exception as e:
        print(f"âŒ Erreur lors de l'envoi d'email Ã  {to_email}: {e}")
        return False


def generate_ics_content(event_title: str, event_description: str, start_datetime: datetime, 
                        end_datetime: datetime, location: str = "Club Municipal de Tennis Chihia") -> str:
    """GÃ©nÃ¨re le contenu d'un fichier ICS (iCalendar).
    
    Args:
        event_title: Titre de l'Ã©vÃ©nement
        event_description: Description de l'Ã©vÃ©nement
        start_datetime: Date et heure de dÃ©but
        end_datetime: Date et heure de fin
        location: Lieu de l'Ã©vÃ©nement
        
    Returns:
        Contenu du fichier ICS
    """
    # Format des dates pour ICS
    def format_datetime(dt):
        return dt.strftime("%Y%m%dT%H%M%SZ")
    
    # PrÃ©parer la description en Ã©chappant les caractÃ¨res spÃ©ciaux
    description = event_description.replace(chr(10), '\\n').replace(chr(13), '')
    
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//CMTCH//Tennis Club//FR
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uuid.uuid4()}@cmtch.tn
DTSTAMP:{format_datetime(datetime.utcnow())}
DTSTART:{format_datetime(start_datetime)}
DTEND:{format_datetime(end_datetime)}
SUMMARY:{event_title}
DESCRIPTION:{description}
LOCATION:{location}
STATUS:CONFIRMED
SEQUENCE:0
END:VEVENT
END:VCALENDAR"""
    
    return ics_content


def send_reservation_confirmation_email(user_email: str, user_name: str, reservation_data: Dict) -> bool:
    """Envoie un email de confirmation de rÃ©servation.
    
    Args:
        user_email: Email de l'utilisateur
        user_name: Nom de l'utilisateur
        reservation_data: DonnÃ©es de la rÃ©servation
        
    Returns:
        True si l'email a Ã©tÃ© envoyÃ© avec succÃ¨s
    """
    subject = f"Confirmation de rÃ©servation - Court {reservation_data['court_number']}"
    
    # Contenu texte
    text_content = f"""
Confirmation de rÃ©servation - Club Municipal de Tennis Chihia

Bonjour {user_name},

Votre rÃ©servation a Ã©tÃ© confirmÃ©e avec succÃ¨s.

DÃ©tails de la rÃ©servation :
- Date : {reservation_data['date']}
- Heure : {reservation_data['start_time']} - {reservation_data['end_time']}
- Court : {reservation_data['court_number']}
- ID rÃ©servation : #{reservation_data['id']}

Lieu : Club Municipal de Tennis Chihia

Merci de votre confiance !

L'Ã©quipe du Club Municipal de Tennis Chihia
"""
    
    # Contenu HTML
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 10px 10px; }}
        .reservation-details {{ background: white; padding: 15px; margin: 15px 0; border-radius: 5px; border-left: 4px solid #667eea; }}
        .detail-item {{ margin: 10px 0; }}
        .label {{ font-weight: bold; color: #667eea; }}
        .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ðŸŽ¾ Confirmation de rÃ©servation</h1>
            <p>Club Municipal de Tennis Chihia</p>
        </div>
        <div class="content">
            <p>Bonjour <strong>{user_name}</strong>,</p>
            <p>Votre rÃ©servation a Ã©tÃ© confirmÃ©e avec succÃ¨s !</p>
            
            <div class="reservation-details">
                <h3>ðŸ“… DÃ©tails de votre rÃ©servation</h3>
                <div class="detail-item">
                    <span class="label">Date :</span> {reservation_data['date']}
                </div>
                <div class="detail-item">
                    <span class="label">Heure :</span> {reservation_data['start_time']} - {reservation_data['end_time']}
                </div>
                <div class="detail-item">
                    <span class="label">Court :</span> Court {reservation_data['court_number']}
                </div>
                <div class="detail-item">
                    <span class="label">ID rÃ©servation :</span> #{reservation_data['id']}
                </div>
            </div>
            
            <p><strong>Lieu :</strong> Club Municipal de Tennis Chihia</p>
            
            <p>Merci de votre confiance !</p>
            <p>Ã€ bientÃ´t sur les courts ! ðŸŽ¾</p>
        </div>
        <div class="footer">
            <p>Club Municipal de Tennis Chihia</p>
            <p>Cet email a Ã©tÃ© envoyÃ© automatiquement, merci de ne pas y rÃ©pondre.</p>
        </div>
    </div>
</body>
</html>
"""
    
    return send_email(user_email, subject, html_content, text_content)


def send_member_validation_email(user_email: str, user_name: str, admin_name: str = "l'administrateur") -> bool:
    """Envoie un email de validation de membre.
    
    Args:
        user_email: Email de l'utilisateur
        user_name: Nom de l'utilisateur
        admin_name: Nom de l'administrateur qui a validÃ©
        
    Returns:
        True si l'email a Ã©tÃ© envoyÃ© avec succÃ¨s
    """
    subject = "Votre compte a Ã©tÃ© validÃ© - Club Municipal de Tennis Chihia"
    
    # Contenu texte
    text_content = f"""
Validation de compte - Club Municipal de Tennis Chihia

Bonjour {user_name},

Excellente nouvelle ! Votre compte a Ã©tÃ© validÃ© par {admin_name}.

Vous pouvez maintenant :
- Vous connecter Ã  votre espace personnel
- Effectuer des rÃ©servations de courts
- AccÃ©der Ã  toutes les fonctionnalitÃ©s du club

Connectez-vous dÃ¨s maintenant sur notre site web !

L'Ã©quipe du Club Municipal de Tennis Chihia
"""
    
    # Contenu HTML
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 10px 10px; }}
        .success-box {{ background: white; padding: 15px; margin: 15px 0; border-radius: 5px; border-left: 4px solid #28a745; }}
        .cta-button {{ display: inline-block; background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 15px 0; }}
        .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>âœ… Compte validÃ© !</h1>
            <p>Club Municipal de Tennis Chihia</p>
        </div>
        <div class="content">
            <p>Bonjour <strong>{user_name}</strong>,</p>
            <p>Excellente nouvelle ! Votre compte a Ã©tÃ© validÃ© par <strong>{admin_name}</strong>.</p>
            
            <div class="success-box">
                <h3>ðŸŽ‰ Vous pouvez maintenant :</h3>
                <ul>
                    <li>Vous connecter Ã  votre espace personnel</li>
                    <li>Effectuer des rÃ©servations de courts</li>
                    <li>AccÃ©der Ã  toutes les fonctionnalitÃ©s du club</li>
                </ul>
            </div>
            
            <p style="text-align: center;">
                <a href="https://www.cmtch.online/connexion" class="cta-button">
                    ðŸŽ¾ Se connecter maintenant
                </a>
            </p>
            
            <p>Ã€ bientÃ´t sur les courts !</p>
        </div>
        <div class="footer">
            <p>Club Municipal de Tennis Chihia</p>
            <p>Cet email a Ã©tÃ© envoyÃ© automatiquement, merci de ne pas y rÃ©pondre.</p>
        </div>
    </div>
</body>
</html>
"""
    
    return send_email(user_email, subject, html_content, text_content)


def hash_password(password: str) -> str:
    """Retourne l'empreinte bcrypt d'un mot de passe en clair."""
    return secure_hash_password(password)


# SYSTÃˆME DE SAUVEGARDE AUTOMATIQUE POUR RENDER
# Ce systÃ¨me sauvegarde et restaure automatiquement les donnÃ©es
# pour Ã©viter la perte lors des redÃ©marrages de Render

def backup_database():
    """CrÃ©e une sauvegarde de la base de donnÃ©es."""
    try:
        import shutil
        from datetime import datetime
        
        # CrÃ©er le dossier de sauvegarde s'il n'existe pas
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        
        # Nom du fichier de sauvegarde avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db"
        backup_path = backup_dir / backup_filename
        
        # VÃ©rifier le type de base de donnÃ©es
        database_url = os.getenv('DATABASE_URL')
        
        if database_url and 'mysql://' in database_url:
            # Pour MySQL, on ne peut pas faire une copie directe du fichier
            # On va exporter les donnÃ©es en SQL
            return backup_mysql_database(backup_path)
        elif database_url:
            # Pour PostgreSQL, on ne peut pas faire une copie directe du fichier
            # On va exporter les donnÃ©es en SQL
            return backup_postgresql_database(backup_path)
        else:
            # Pour SQLite, on peut copier le fichier directement
            source_db = Path("database.db")
            if source_db.exists():
                shutil.copy2(source_db, backup_path)
                print(f"âœ… Sauvegarde SQLite crÃ©Ã©e: {backup_path}")
                return str(backup_path)
            else:
                print("âŒ Fichier de base de donnÃ©es SQLite non trouvÃ©")
                return None
                
    except Exception as e:
        print(f"âŒ Erreur lors de la sauvegarde: {e}")
        return None

def backup_mysql_database(backup_path):
    """CrÃ©e une sauvegarde de la base de donnÃ©es MySQL."""
    try:
        import mysql.connector
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return None
            
        # Parser l'URL MySQL
        url_parts = database_url.replace('mysql://', '').split('@')
        user_pass = url_parts[0].split(':')
        host_db = url_parts[1].split('/')
        host_port = host_db[0].split(':')
        
        user = user_pass[0]
        password = user_pass[1]
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 3306
        database = host_db[1]
        
        # Connexion Ã  MySQL
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        # CrÃ©er le fichier de sauvegarde SQL
        sql_backup_path = str(backup_path).replace('.db', '.sql')
        
        with open(sql_backup_path, 'w', encoding='utf-8') as f:
            # Obtenir la liste des tables
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                f.write(f"\n-- Table: {table_name}\n")
                f.write(f"DROP TABLE IF EXISTS `{table_name}`;\n")
                
                # Obtenir la structure de la table
                cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                create_table = cursor.fetchone()
                f.write(f"{create_table[1]};\n\n")
                
                # Obtenir les donnÃ©es de la table
                cursor.execute(f"SELECT * FROM `{table_name}`")
                rows = cursor.fetchall()
                
                if rows:
                    # Obtenir les noms des colonnes
                    cursor.execute(f"DESCRIBE `{table_name}`")
                    columns = [col[0] for col in cursor.fetchall()]
                    
                    for row in rows:
                        values = []
                        for value in row:
                            if value is None:
                                values.append('NULL')
                            elif isinstance(value, str):
                                values.append(f"'{value.replace(chr(39), chr(39)+chr(39))}'")
                            else:
                                values.append(str(value))
                        
                        f.write(f"INSERT INTO `{table_name}` (`{'`, `'.join(columns)}`) VALUES ({', '.join(values)});\n")
        
        conn.close()
        print(f"âœ… Sauvegarde MySQL crÃ©Ã©e: {sql_backup_path}")
        return sql_backup_path
        
    except Exception as e:
        print(f"âŒ Erreur lors de la sauvegarde MySQL: {e}")
        return None

def backup_postgresql_database(backup_path):
    """CrÃ©e une sauvegarde de la base de donnÃ©es PostgreSQL."""
    try:
        import psycopg2
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return None
            
        # Connexion Ã  PostgreSQL
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # CrÃ©er le fichier de sauvegarde SQL
        sql_backup_path = str(backup_path).replace('.db', '.sql')
        
        with open(sql_backup_path, 'w', encoding='utf-8') as f:
            # Obtenir la liste des tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                f.write(f"\n-- Table: {table_name}\n")
                f.write(f"DROP TABLE IF EXISTS \"{table_name}\" CASCADE;\n")
                
                # Obtenir la structure de la table
                cursor.execute(f"""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}' AND table_schema = 'public'
                    ORDER BY ordinal_position
                """)
                columns = cursor.fetchall()
                
                if columns:
                    f.write(f"CREATE TABLE \"{table_name}\" (\n")
                    column_defs = []
                    for col in columns:
                        col_name, data_type, is_nullable, default_val = col
                        col_def = f'    "{col_name}" {data_type}'
                        if is_nullable == 'NO':
                            col_def += ' NOT NULL'
                        if default_val:
                            col_def += f' DEFAULT {default_val}'
                        column_defs.append(col_def)
                    f.write(',\n'.join(column_defs))
                    f.write("\n);\n\n")
                
                # Obtenir les donnÃ©es de la table
                cursor.execute(f'SELECT * FROM "{table_name}"')
                rows = cursor.fetchall()
                
                if rows:
                    # Obtenir les noms des colonnes
                    column_names = [desc[0] for desc in cursor.description]
                    
                    for row in rows:
                        values = []
                        for value in row:
                            if value is None:
                                values.append('NULL')
                            elif isinstance(value, str):
                                values.append(f"'{value.replace(chr(39), chr(39)+chr(39))}'")
                            else:
                                values.append(str(value))
                        
                        columns_str = '", "'.join(column_names)
                        f.write(f'INSERT INTO "{table_name}" ("{columns_str}") VALUES ({", ".join(values)});\n')
        
        conn.close()
        print(f"âœ… Sauvegarde PostgreSQL crÃ©Ã©e: {sql_backup_path}")
        return sql_backup_path
        
    except Exception as e:
        print(f"âŒ Erreur lors de la sauvegarde PostgreSQL: {e}")
        return None

def find_latest_backup():
    """Trouve la sauvegarde la plus rÃ©cente."""
    try:
        backup_dir = Path("backups")
        if not backup_dir.exists():
            return None
            
        # Chercher les fichiers de sauvegarde
        backup_files = []
        for file_path in backup_dir.glob("backup_*.db"):
            backup_files.append(file_path)
        for file_path in backup_dir.glob("backup_*.sql"):
            backup_files.append(file_path)
            
        if not backup_files:
            return None
            
        # Retourner le fichier le plus rÃ©cent
        latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
        return str(latest_backup)
        
    except Exception as e:
        print(f"âŒ Erreur lors de la recherche de sauvegarde: {e}")
        return None

def restore_database(backup_path):
    """Restaure la base de donnÃ©es depuis une sauvegarde."""
    try:
        backup_path = Path(backup_path)
        if not backup_path.exists():
            print(f"âŒ Fichier de sauvegarde non trouvÃ©: {backup_path}")
            return False
            
        # VÃ©rifier le type de base de donnÃ©es
        database_url = os.getenv('DATABASE_URL')
        
        if database_url and 'mysql://' in database_url:
            return restore_mysql_database(backup_path)
        elif database_url:
            return restore_postgresql_database(backup_path)
        else:
            return restore_sqlite_database(backup_path)
            
    except Exception as e:
        print(f"âŒ Erreur lors de la restauration: {e}")
        return False

def restore_sqlite_database(backup_path):
    """Restaure la base de donnÃ©es SQLite depuis une sauvegarde."""
    try:
        import shutil
        
        # Sauvegarder la base actuelle
        current_db = Path("database.db")
        if current_db.exists():
            backup_current = Path("database_backup_before_restore.db")
            shutil.copy2(current_db, backup_current)
            print(f"âœ… Sauvegarde de la base actuelle: {backup_current}")
        
        # Restaurer depuis la sauvegarde
        shutil.copy2(backup_path, current_db)
        print(f"âœ… Base de donnÃ©es SQLite restaurÃ©e depuis: {backup_path}")
        return True
        
    except Exception as e:
        print(f"âŒ Erreur lors de la restauration SQLite: {e}")
        return False

def restore_mysql_database(backup_path):
    """Restaure la base de donnÃ©es MySQL depuis une sauvegarde."""
    try:
        import mysql.connector
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return False
            
        # Parser l'URL MySQL
        url_parts = database_url.replace('mysql://', '').split('@')
        user_pass = url_parts[0].split(':')
        host_db = url_parts[1].split('/')
        host_port = host_db[0].split(':')
        
        user = user_pass[0]
        password = user_pass[1]
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 3306
        database = host_db[1]
        
        # Connexion Ã  MySQL
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        # Lire et exÃ©cuter le fichier SQL
        with open(backup_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
            
        cursor = conn.cursor()
        
        # ExÃ©cuter les commandes SQL une par une
        for statement in sql_content.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                except Exception as e:
                    print(f"âš ï¸ Erreur lors de l'exÃ©cution de: {statement[:50]}... - {e}")
        
        conn.commit()
        conn.close()
        print(f"âœ… Base de donnÃ©es MySQL restaurÃ©e depuis: {backup_path}")
        return True
        
    except Exception as e:
        print(f"âŒ Erreur lors de la restauration MySQL: {e}")
        return False

def restore_postgresql_database(backup_path):
    """Restaure la base de donnÃ©es PostgreSQL depuis une sauvegarde."""
    try:
        import psycopg2
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return False
            
        # Connexion Ã  PostgreSQL
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Lire et exÃ©cuter le fichier SQL
        with open(backup_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
            
        # ExÃ©cuter les commandes SQL une par une
        for statement in sql_content.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                except Exception as e:
                    print(f"âš ï¸ Erreur lors de l'exÃ©cution de: {statement[:50]}... - {e}")
        
        conn.commit()
        conn.close()
        print(f"âœ… Base de donnÃ©es PostgreSQL restaurÃ©e depuis: {backup_path}")
        return True
        
    except Exception as e:
        print(f"âŒ Erreur lors de la restauration PostgreSQL: {e}")
        return False

def auto_backup_system():
    """SystÃ¨me de sauvegarde automatique pour prÃ©server les donnÃ©es sur Render."""
    try:
        print("ðŸ”„ DÃ©marrage du systÃ¨me de sauvegarde automatique...")
        
        # VÃ©rifier si le systÃ¨me est dÃ©sactivÃ©
        flag_file = Path("DISABLE_AUTO_BACKUP")
        if flag_file.exists():
            print("ðŸš« SystÃ¨me de sauvegarde automatique dÃ©sactivÃ© par l'utilisateur")
            return
        
        # VÃ©rifier si on est sur Render (prÃ©sence de DATABASE_URL)
        if not os.getenv('DATABASE_URL'):
            print("â„¹ï¸ Pas sur Render - systÃ¨me de sauvegarde ignorÃ©")
            return
        
        # VÃ©rifier d'abord si la base de donnÃ©es contient des donnÃ©es
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # VÃ©rifier si la table users existe et contient des donnÃ©es
            cur.execute("SELECT COUNT(*) FROM users")
            users_count = cur.fetchone()[0]
            
            if users_count > 0:
                print(f"âœ… Base de donnÃ©es contient {users_count} utilisateur(s) - Sauvegarde uniquement")
                # Si des donnÃ©es existent, faire seulement une sauvegarde
                backup_file = backup_database()
                if backup_file:
                    print(f"âœ… Sauvegarde crÃ©Ã©e: {backup_file}")
                else:
                    print("âš ï¸ Ã‰chec de la sauvegarde")
            else:
                print("ðŸ“­ Base de donnÃ©es vide - Tentative de restauration")
                # Si la base est vide, essayer de restaurer
                latest_backup = find_latest_backup()
                if latest_backup:
                    print(f"ðŸ”„ Restauration depuis {latest_backup}")
                    if restore_database(latest_backup):
                        print("âœ… Restauration rÃ©ussie")
                    else:
                        print("âŒ Ã‰chec de la restauration")
                else:
                    print("ðŸ“­ Aucune sauvegarde trouvÃ©e")
                    
        except Exception as e:
            print(f"âŒ Erreur lors de la vÃ©rification de la base: {e}")
        finally:
            conn.close()
            
    except Exception as e:
        print(f"âŒ Erreur dans le systÃ¨me de sauvegarde automatique: {e}")

#
# Si vous voulez l'activer, utilisez l'endpoint /enable-auto-backup
# Si vous voulez le dÃ©sactiver, utilisez l'endpoint /disable-auto-backup
#
# auto_backup_system()


def get_current_user(request: Request) -> Optional[sqlite3.Row]:
    """Retourne l'utilisateur actuellement connectÃ© Ã  partir du cookie de session.

    Args:
        request: L'objet Request en cours.

    Returns:
        Une ligne reprÃ©sentant l'utilisateur, ou None si aucun utilisateur
        n'est authentifiÃ©.
    """
    token = request.cookies.get("session_token")
    if not token:
        return None
    
    # RÃ©cupÃ©rer l'IP et user agent pour la validation
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # Valider le token avec le nouveau systÃ¨me sÃ©curisÃ©
    user_id = validate_session_token(token, ip_address)
    if not user_id:
        return None
    
    # RÃ©cupÃ©rer les informations de l'utilisateur
    conn = get_db_connection()
    try:
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            # Utiliser le curseur MySQL avec noms de colonnes
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            cur, column_names = execute_with_names("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()
            user = convert_mysql_result(user, column_names)
        else:
            # Connexion SQLite/PostgreSQL normale
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user = cur.fetchone()
        
        return user
    finally:
        conn.close()


def require_login(request: Request) -> sqlite3.Row:
    """DÃ©corateur simple pour s'assurer qu'un utilisateur est connectÃ©.

    Si aucun utilisateur n'est connectÃ©, redirige vers la page de connexion.

    Args:
        request: L'objet Request en cours.

    Returns:
        La ligne reprÃ©sentant l'utilisateur connectÃ©.
    """
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=302, detail="Not authenticated")
    return user


@app.on_event("startup")
async def startup() -> None:
    """AppelÃ© au dÃ©marrage de l'application."""
    print("ðŸš€ DÃ©marrage de l'application...")
    
    # IMPORTANT : AUCUNE initialisation automatique de la base de donnÃ©es
    # Les tables et donnÃ©es existantes doivent Ãªtre prÃ©servÃ©es
    print("â„¹ï¸ Initialisation automatique de la base de donnÃ©es dÃ©sactivÃ©e")
    print("â„¹ï¸ Les donnÃ©es existantes sont prÃ©servÃ©es")
    
    # VÃ©rifier seulement la connexion Ã  la base
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Compter les donnÃ©es existantes
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM articles")
        articles_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM reservations")
        reservations_count = cur.fetchone()[0]
        
        print(f"ðŸ“Š Ã‰tat de la base de donnÃ©es au dÃ©marrage :")
        print(f"   - Utilisateurs : {users_count}")
        print(f"   - Articles : {articles_count}")
        print(f"   - RÃ©servations : {reservations_count}")
        
        conn.close()
        
    except Exception as e:
        print(f"âš ï¸ Impossible de vÃ©rifier l'Ã©tat de la base : {e}")
    
    # Nettoyer les sessions expirÃ©es au dÃ©marrage
    try:
        cleanup_expired_sessions()
        print("âœ… Nettoyage des sessions expirÃ©es effectuÃ©")
    except Exception as e:
        print(f"âš ï¸ Erreur lors du nettoyage des sessions : {e}")
    
    print("ðŸŽ‰ Application prÃªte !")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """Page d'accueil du site.

    Affiche une prÃ©sentation du club, les coordonnÃ©es et un lien vers les
    diffÃ©rentes sections selon le rÃ´le de l'utilisateur.
    """
    user = get_current_user(request)
    # Informations publiques sur le club provenant de sources fiables.
    adresse = "Route Teboulbi km 6, 3041 Sfax sud"
    telephone = "+216 29 60 03 40"
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


@app.get("/inscription", response_class=HTMLResponse)
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


@app.post("/inscription", response_class=HTMLResponse)
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


@app.get("/verifier-email/{token}", response_class=HTMLResponse)
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


@app.get("/connexion", response_class=HTMLResponse)
async def login_form(request: Request) -> HTMLResponse:
    """Affiche le formulaire de connexion."""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/connexion", response_class=HTMLResponse)
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
            # Connexion SQLite/PostgreSQL normale
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username = ?", (username,))
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


@app.get("/deconnexion")
async def logout(request: Request) -> RedirectResponse:
    """Termine la session de l'utilisateur."""
    token = request.cookies.get("session_token")
    if token:
        # DÃ©sactiver la session en base de donnÃ©es
        deactivate_session(token)
    
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_token")
    return response


@app.get("/admin/cleanup-sessions")
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


@app.get("/admin/create-sessions-table")
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


@app.get("/create-sessions-table")
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


def check_admin(user: sqlite3.Row) -> None:
    """LÃ¨ve une exception si l'utilisateur n'est pas administrateur."""
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="AccÃ¨s rÃ©servÃ© Ã  l'administration.")


@app.get("/reservations", response_class=HTMLResponse)
async def reservations_page(request: Request) -> HTMLResponse:
    """Affiche la page de rÃ©servation pour les membres validÃ©s.

    Montre les rÃ©servations existantes pour le jour sÃ©lectionnÃ© et permet
    d'effectuer une nouvelle rÃ©servation si l'horaire est libre.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    if not user.validated:
        return templates.TemplateResponse(
            "not_validated.html",
            {"request": request, "message": "Votre inscription doit Ãªtre validÃ©e pour accÃ©der aux rÃ©servations."},
        )
    
    # ParamÃ¨tres de la requÃªte
    today_str = date.today().isoformat()
    selected_date = request.query_params.get("date", today_str)
    view_type = request.query_params.get("view", "day")  # day, week, month
    
    # Calculer les dates de la semaine si vue semaine
    week_start = None
    week_end = None
    week_dates = []
    
    if view_type == "week":
        selected_date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
        # Trouver le lundi de la semaine
        days_since_monday = selected_date_obj.weekday()
        week_start = selected_date_obj - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)
        
        # GÃ©nÃ©rer toutes les dates de la semaine avec informations formatÃ©es
        current_date = week_start
        while current_date <= week_end:
            day_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
            day_index = current_date.weekday()
            week_dates.append({
                "date": current_date.isoformat(),
                "day_name": day_names[day_index],
                "day_number": current_date.day
            })
            current_date += timedelta(days=1)
    
    # RÃ©cupÃ©rer les rÃ©servations
    conn = get_db_connection()
    
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        from database import get_mysql_cursor_with_names, convert_mysql_result
        execute_with_names = get_mysql_cursor_with_names(conn)
        
        # RÃ©servations pour la date sÃ©lectionnÃ©e ou la semaine
        if view_type == "week" and week_dates:
            # Extraire les dates des objets week_dates
            dates_list = [week_date["date"] for week_date in week_dates]
            placeholders = ','.join(['%s'] * len(dates_list))
            cur, column_names = execute_with_names(
                "SELECT r.*, u.full_name AS user_full_name, u.username FROM reservations r JOIN users u ON r.user_id = u.id "
                "WHERE date IN (" + placeholders + ") ORDER BY date, start_time",
                dates_list,
            )
        else:
            cur, column_names = execute_with_names(
                "SELECT r.*, u.full_name AS user_full_name, u.username FROM reservations r JOIN users u ON r.user_id = u.id "
                "WHERE date = %s ORDER BY start_time",
                (selected_date,),
            )
        reservations = cur.fetchall()
        reservations = [convert_mysql_result(res, column_names) for res in reservations]
        
        # RÃ©servations de l'utilisateur (toutes)
        cur, column_names = execute_with_names(
            "SELECT * FROM reservations WHERE user_id = %s ORDER BY date DESC, start_time",
            (user.id,),
        )
        user_reservations = cur.fetchall()
        user_reservations = [convert_mysql_result(res, column_names) for res in user_reservations]
        
        # Statistiques utilisateur
        cur, column_names = execute_with_names(
            "SELECT COUNT(*) as total_reservations, COUNT(DISTINCT date) as days_played FROM reservations WHERE user_id = %s",
            (user.id,),
        )
        stats = cur.fetchone()
        user_stats = convert_mysql_result(stats, column_names) if stats else {"total_reservations": 0, "days_played": 0}
        
    else:
        cur = conn.cursor()
        if view_type == "week" and week_dates:
            # Extraire les dates des objets week_dates
            dates_list = [week_date["date"] for week_date in week_dates]
            placeholders = ','.join(['?'] * len(dates_list))
            cur.execute(
                "SELECT r.*, u.full_name AS user_full_name, u.username FROM reservations r JOIN users u ON r.user_id = u.id "
                "WHERE date IN (" + placeholders + ") ORDER BY date, start_time",
                dates_list,
            )
        else:
            cur.execute(
                "SELECT r.*, u.full_name AS user_full_name, u.username FROM reservations r JOIN users u ON r.user_id = u.id "
                "WHERE date = ? ORDER BY start_time",
                (selected_date,),
            )
        reservations = cur.fetchall()
        
        cur.execute(
            "SELECT * FROM reservations WHERE user_id = ? ORDER BY date DESC, start_time",
            (user.id,),
        )
        user_reservations = cur.fetchall()
        
        # Statistiques utilisateur
        cur.execute(
            "SELECT COUNT(*) as total_reservations, COUNT(DISTINCT date) as days_played FROM reservations WHERE user_id = ?",
            (user.id,),
        )
        stats = cur.fetchone()
        user_stats = {"total_reservations": stats[0], "days_played": stats[1]} if stats else {"total_reservations": 0, "days_played": 0}
    
    conn.close()
    
    # GÃ©nÃ©rer des crÃ©neaux horaires amÃ©liorÃ©s (6h-23h)
    time_slots: List[Tuple[str, str]] = []
    for hour in range(6, 23):
        start_slot = time(hour, 0)
        end_slot = time(hour + 1, 0) if hour < 22 else time(23, 0)
        time_slots.append((start_slot.strftime("%H:%M"), end_slot.strftime("%H:%M")))
    
    # PrÃ©parer la disponibilitÃ© avec informations enrichies
    availability: Dict[int, Dict[Tuple[str, str], dict]] = {1: {}, 2: {}, 3: {}}
    reservations_by_court = {1: [], 2: [], 3: []}
    
    for res in reservations:
        reservations_by_court[res.court_number].append(res)
    
    # Pour chaque court et chaque crÃ©neau, dÃ©terminer la disponibilitÃ©
    for court in (1, 2, 3):
        court_reservations = reservations_by_court.get(court, [])
        for start_str, end_str in time_slots:
            reserved = False
            reservation_info = None
            
            for res in court_reservations:
                # Gestion des timedelta MySQL
                start_time_str = str(res.start_time) if hasattr(res.start_time, 'total_seconds') else res.start_time
                end_time_str = str(res.end_time) if hasattr(res.end_time, 'total_seconds') else res.end_time
                
                if hasattr(res.start_time, 'total_seconds'):
                    total_seconds = int(res.start_time.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    start_time_str = f"{hours:02d}:{minutes:02d}"
                
                if hasattr(res.end_time, 'total_seconds'):
                    total_seconds = int(res.end_time.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    end_time_str = f"{hours:02d}:{minutes:02d}"
                
                res_start = datetime.strptime(start_time_str, "%H:%M").time()
                res_end = datetime.strptime(end_time_str, "%H:%M").time()
                slot_start = datetime.strptime(start_str, "%H:%M").time()
                slot_end = datetime.strptime(end_str, "%H:%M").time()
                
                if (res_start < slot_end and res_end > slot_start):
                    reserved = True
                    reservation_info = {
                        "user_full_name": res.user_full_name,
                        "username": getattr(res, 'username', "Utilisateur"),
                        "is_current_user": res.user_id == user.id
                    }
                    break
            availability[court][(start_str, end_str)] = {
                "reserved": reserved,
                "reservation_info": reservation_info
            }
    
    # PrÃ©parer les donnÃ©es pour la vue semaine (disponibilitÃ© par court et par jour)
    week_availability = {}
    month_availability = {}
    
    if view_type == "week" and week_dates:
        for week_date in week_dates:
            date_str = week_date["date"]
            week_availability[date_str] = {}
            
            for court in (1, 2, 3):
                week_availability[date_str][court] = {}
                for start_str, end_str in time_slots:
                    # Chercher les rÃ©servations pour ce court, cette date et ce crÃ©neau
                    reserved = False
                    reservation_info = None
                    
                    for res in reservations:
                        if (res.court_number == court and 
                            res.date == date_str):
                            
                            # Gestion des timedelta MySQL
                            start_time_str = str(res.start_time) if hasattr(res.start_time, 'total_seconds') else res.start_time
                            end_time_str = str(res.end_time) if hasattr(res.end_time, 'total_seconds') else res.end_time
                            
                            if hasattr(res.start_time, 'total_seconds'):
                                total_seconds = int(res.start_time.total_seconds())
                                hours = total_seconds // 3600
                                minutes = (total_seconds % 3600) // 60
                                start_time_str = f"{hours:02d}:{minutes:02d}"
                            
                            if hasattr(res.end_time, 'total_seconds'):
                                total_seconds = int(res.end_time.total_seconds())
                                hours = total_seconds // 3600
                                minutes = (total_seconds % 3600) // 60
                                end_time_str = f"{hours:02d}:{minutes:02d}"
                            
                            res_start = datetime.strptime(start_time_str, "%H:%M").time()
                            res_end = datetime.strptime(end_time_str, "%H:%M").time()
                            slot_start = datetime.strptime(start_str, "%H:%M").time()
                            slot_end = datetime.strptime(end_str, "%H:%M").time()
                            
                            if (res_start < slot_end and res_end > slot_start):
                                reserved = True
                                reservation_info = {
                                    "user_full_name": res.user_full_name,
                                    "username": getattr(res, 'username', "Utilisateur"),
                                    "is_current_user": res.user_id == user.id
                                }
                                break
                    
                    week_availability[date_str][court][(start_str, end_str)] = {
                        "reserved": reserved,
                        "reservation_info": reservation_info
                    }
    
    # PrÃ©parer les donnÃ©es pour la vue mois
    if view_type == "month":
        # Calculer le dÃ©but et la fin du mois
        selected_date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
        month_start = selected_date_obj.replace(day=1)
        
        # Formater le titre du mois
        month_names = [
            "Janvier", "FÃ©vrier", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "AoÃ»t", "Septembre", "Octobre", "Novembre", "DÃ©cembre"
        ]
        month_title = f"{month_names[selected_date_obj.month - 1]} {selected_date_obj.year}"
        
        # Trouver le dernier jour du mois
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
        
        # GÃ©nÃ©rer toutes les dates du mois
        month_dates = []
        current_date = month_start
        while current_date <= month_end:
            month_dates.append({
                "date": current_date.isoformat(),
                "day_number": current_date.day,
                "is_current_month": True
            })
            current_date += timedelta(days=1)
        
        # Ajouter les jours de la semaine prÃ©cÃ©dente pour complÃ©ter la premiÃ¨re semaine
        days_before = month_start.weekday()
        for i in range(days_before - 1, -1, -1):
            prev_date = month_start - timedelta(days=i + 1)
            month_dates.insert(0, {
                "date": prev_date.isoformat(),
                "day_number": prev_date.day,
                "is_current_month": False
            })
        
        # Ajouter les jours de la semaine suivante pour complÃ©ter la derniÃ¨re semaine
        days_after = 6 - month_end.weekday()
        for i in range(1, days_after + 1):
            next_date = month_end + timedelta(days=i)
            month_dates.append({
                "date": next_date.isoformat(),
                "day_number": next_date.day,
                "is_current_month": False
            })
        
        # Calculer la disponibilitÃ© pour chaque jour du mois
        for date_info in month_dates:
            date_str = date_info["date"]
            month_availability[date_str] = {}
            
            for court in (1, 2, 3):
                month_availability[date_str][court] = {}
                for start_str, end_str in time_slots:
                    reserved = False
                    reservation_info = None
                    
                    for res in reservations:
                        if (res.court_number == court and 
                            res.date == date_str):
                            
                            # Gestion des timedelta MySQL
                            start_time_str = str(res.start_time) if hasattr(res.start_time, 'total_seconds') else res.start_time
                            end_time_str = str(res.end_time) if hasattr(res.end_time, 'total_seconds') else res.end_time
                            
                            if hasattr(res.start_time, 'total_seconds'):
                                total_seconds = int(res.start_time.total_seconds())
                                hours = total_seconds // 3600
                                minutes = (total_seconds % 3600) // 60
                                start_time_str = f"{hours:02d}:{minutes:02d}"
                            
                            if hasattr(res.end_time, 'total_seconds'):
                                total_seconds = int(res.end_time.total_seconds())
                                hours = total_seconds // 3600
                                minutes = (total_seconds % 3600) // 60
                                end_time_str = f"{hours:02d}:{minutes:02d}"
                            
                            res_start = datetime.strptime(start_time_str, "%H:%M").time()
                            res_end = datetime.strptime(end_time_str, "%H:%M").time()
                            slot_start = datetime.strptime(start_str, "%H:%M").time()
                            slot_end = datetime.strptime(end_str, "%H:%M").time()
                            
                            if (res_start < slot_end and res_end > slot_start):
                                reserved = True
                                reservation_info = {
                                    "user_full_name": res.user_full_name,
                                    "username": getattr(res, 'username', "Utilisateur"),
                                    "is_current_user": res.user_id == user.id
                                }
                                break
                    
                    month_availability[date_str][court][(start_str, end_str)] = {
                        "reserved": reserved,
                        "reservation_info": reservation_info
                    }
    
    # PrÃ©parer les donnÃ©es pour le template
    template_data = {
        "request": request,
        "user": user,
        "is_admin": bool(user.is_admin),
        "reservations": reservations,
        "user_reservations": user_reservations,
        "user_stats": user_stats,
        "selected_date": selected_date,
        "time_slots": time_slots,
        "availability": availability,
        "week_availability": week_availability,
        "month_availability": month_availability,
        "view_type": view_type,
        "week_start": week_start.isoformat() if week_start else None,
        "week_end": week_end.isoformat() if week_end else None,
        "week_dates": week_dates,
        "month_dates": month_dates if view_type == "month" else None,
        "month_title": month_title if view_type == "month" else None,
        "today_date": today_str,
    }
    
    return templates.TemplateResponse("reservations.html", template_data)


@app.post("/reservations", response_class=HTMLResponse)
async def create_reservation(request: Request) -> HTMLResponse:
    """CrÃ©e une rÃ©servation si l'horaire est disponible.

    VÃ©rifie les conflits avec les rÃ©servations existantes sur le mÃªme court
    avant d'insÃ©rer une nouvelle ligne.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    if not user.validated:
        return templates.TemplateResponse(
            "not_validated.html",
            {"request": request, "message": "Votre inscription doit Ãªtre validÃ©e pour accÃ©der aux rÃ©servations."},
        )
    raw_body = await request.body()
    form = urllib.parse.parse_qs(raw_body.decode(), keep_blank_values=True)
    date_field = form.get("date", [""])[0]
    court_number_raw = form.get("court_number", [""])[0]
    start_time = form.get("start_time", [""])[0]
    end_time = form.get("end_time", [""])[0]
    # Conversion de court_number
    try:
        court_number = int(court_number_raw)
    except (ValueError, TypeError):
        court_number = None
    errors: List[str] = []
    try:
        _date = datetime.strptime(date_field, "%Y-%m-%d").date()
        _start = datetime.strptime(start_time, "%H:%M").time()
        _end = datetime.strptime(end_time, "%H:%M").time()
        if _start >= _end:
            errors.append("L'heure de fin doit Ãªtre postÃ©rieure Ã  l'heure de dÃ©but.")
    except ValueError:
        errors.append("Format de date ou d'heure invalide.")
    if court_number not in (1, 2, 3):
        errors.append("NumÃ©ro de court invalide.")
    if errors:
        return templates.TemplateResponse(
            "reservation_error.html",
            {
                "request": request,
                "user": user,
                "errors": errors,
                "selected_date": date_field,
            },
        )
    # VÃ©rifier les conflits
    conn = get_db_connection()
    
    # VÃ©rifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM reservations WHERE court_number = %s AND date = %s AND "
            "((start_time < %s AND end_time > %s) OR (start_time < %s AND end_time > %s) OR (start_time >= %s AND end_time <= %s))",
            (
                court_number,
                _date.isoformat(),
                end_time,
                end_time,
                start_time,
                start_time,
                start_time,
                end_time,
            ),
        )
        conflict = cur.fetchone()
    else:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM reservations WHERE court_number = ? AND date = ? AND "
            "((start_time < ? AND end_time > ?) OR (start_time < ? AND end_time > ?) OR (start_time >= ? AND end_time <= ?))",
            (
                court_number,
                _date.isoformat(),
                end_time,
                end_time,
                start_time,
                start_time,
                start_time,
                end_time,
            ),
        )
        conflict = cur.fetchone()
    if conflict:
        conn.close()
        return templates.TemplateResponse(
            "reservation_error.html",
            {
                "request": request,
                "user": user,
                "errors": [
                    "Ce crÃ©neau n'est pas disponible pour le court choisi. Veuillez sÃ©lectionner un autre horaire."
                ],
                "selected_date": date_field,
            },
        )
    # Insertion de la rÃ©servation
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur.execute(
            "INSERT INTO reservations (user_id, court_number, date, start_time, end_time) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user.id, court_number, _date.isoformat(), start_time, end_time),
        )
    else:
        cur.execute(
            "INSERT INTO reservations (user_id, court_number, date, start_time, end_time) "
            "VALUES (?, ?, ?, ?, ?)",
            (user.id, court_number, _date.isoformat(), start_time, end_time),
        )
    # RÃ©cupÃ©rer l'ID de la rÃ©servation crÃ©Ã©e
    reservation_id = cur.lastrowid
    
    conn.commit()
    conn.close()
    
    # Envoyer un email de confirmation
    reservation_data = {
        'id': reservation_id,
        'date': _date.strftime('%d/%m/%Y'),
        'start_time': start_time,
        'end_time': end_time,
        'court_number': court_number
    }
    
    # RÃ©cupÃ©rer les informations de l'utilisateur pour l'email
    conn = get_db_connection()
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        cur.execute("SELECT email, full_name FROM users WHERE id = %s", (user.id,))
        user_info = cur.fetchone()
    else:
        cur = conn.cursor()
        cur.execute("SELECT email, full_name FROM users WHERE id = ?", (user.id,))
        user_info = cur.fetchone()
    conn.close()
    
    if user_info:
        user_email, user_name = user_info
        send_reservation_confirmation_email(user_email, user_name, reservation_data)
    
    redirect_url = f"/reservations?date={_date.isoformat()}"
    return RedirectResponse(url=redirect_url, status_code=303)


@app.get("/reservations/{reservation_id}/export-ics")
async def export_reservation_ics(request: Request, reservation_id: int) -> FileResponse:
    """Exporte une rÃ©servation vers un fichier ICS pour le calendrier personnel."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Non autorisÃ©")
    
    conn = get_db_connection()
    
    # RÃ©cupÃ©rer les dÃ©tails de la rÃ©servation
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        cur.execute(
            "SELECT r.*, u.full_name FROM reservations r JOIN users u ON r.user_id = u.id WHERE r.id = %s",
            (reservation_id,)
        )
        reservation = cur.fetchone()
    else:
        cur = conn.cursor()
        cur.execute(
            "SELECT r.*, u.full_name FROM reservations r JOIN users u ON r.user_id = u.id WHERE r.id = ?",
            (reservation_id,)
        )
        reservation = cur.fetchone()
    
    conn.close()
    
    if not reservation:
        raise HTTPException(status_code=404, detail="RÃ©servation introuvable")
    
    # VÃ©rifier que l'utilisateur est propriÃ©taire de la rÃ©servation ou admin
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        reservation_user_id = reservation[1]  # user_id est Ã  l'index 1
        reservation_full_name = reservation[5]  # full_name est Ã  l'index 5
    else:
        reservation_user_id = reservation['user_id']
        reservation_full_name = reservation['full_name']
    
    if reservation_user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="AccÃ¨s non autorisÃ©")
    
    # Convertir les donnÃ©es de la rÃ©servation
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        # MySQL retourne un tuple
        date_str = reservation[3]  # date
        start_time_str = reservation[4]  # start_time
        end_time_str = reservation[5]  # end_time
        court_number = reservation[2]  # court_number
    else:
        # SQLite retourne un dict
        date_str = reservation['date']
        start_time_str = reservation['start_time']
        end_time_str = reservation['end_time']
        court_number = reservation['court_number']
    
    # Parser les dates et heures
    try:
        # GÃ©rer le cas oÃ¹ date_str est dÃ©jÃ  un objet date (MySQL)
        if isinstance(date_str, date):
            reservation_date = date_str
        else:
            reservation_date = datetime.strptime(str(date_str), "%Y-%m-%d").date()
        
        # GÃ©rer les diffÃ©rents formats de temps (string ou timedelta)
        if isinstance(start_time_str, str):
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
        else:
            # Si c'est un timedelta (MySQL)
            total_seconds = int(start_time_str.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            start_time = time(hours, minutes)
        
        if isinstance(end_time_str, str):
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
        else:
            # Si c'est un timedelta (MySQL)
            total_seconds = int(end_time_str.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            end_time = time(hours, minutes)
        
        # CrÃ©er les datetime complets
        start_datetime = datetime.combine(reservation_date, start_time)
        end_datetime = datetime.combine(reservation_date, end_time)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur de format de date: {e}")
    
    # GÃ©nÃ©rer le contenu ICS
    event_title = f"Tennis - Court {court_number}"
    event_description = f"RÃ©servation de tennis sur le court {court_number} avec {reservation_full_name}"
    location = "Club Municipal de Tennis Chihia"
    
    ics_content = generate_ics_content(event_title, event_description, start_datetime, end_datetime, location)
    
    # CrÃ©er un fichier temporaire
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ics', delete=False, encoding='utf-8') as f:
        f.write(ics_content)
        temp_file_path = f.name
    
    # Retourner le fichier
    return FileResponse(
        path=temp_file_path,
        filename=f"reservation_tennis_court_{court_number}_{date_str}.ics",
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=reservation_tennis_court_{court_number}_{date_str}.ics"}
    )


# ===== NOUVELLES ROUTES POUR LES FONCTIONNALITÃ‰S AMÃ‰LIORÃ‰ES =====

@app.post("/reservations/recurring", response_class=HTMLResponse)
async def create_recurring_reservation(request: Request) -> HTMLResponse:
    """CrÃ©e une rÃ©servation rÃ©currente."""
    user = get_current_user(request)
    if not user or not user.validated:
        return RedirectResponse(url="/connexion", status_code=303)
    
    form = await request.form()
    court_number = int(form.get("court_number"))
    start_time = form.get("start_time")
    end_time = form.get("end_time")
    frequency = form.get("frequency")  # weekly, biweekly, monthly
    start_date = form.get("start_date")
    end_date = form.get("end_date")
    
    conn = get_db_connection()
    
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO recurring_reservations (user_id, court_number, start_time, end_time, frequency, start_date, end_date, active) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, 1)",
            (user.id, court_number, start_time, end_time, frequency, start_date, end_date)
        )
    else:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO recurring_reservations (user_id, court_number, start_time, end_time, frequency, start_date, end_date, active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            (user.id, court_number, start_time, end_time, frequency, start_date, end_date)
        )
    
    conn.commit()
    conn.close()
    
    return RedirectResponse(url=f"/reservations?date={start_date}", status_code=303)


@app.delete("/reservations/{reservation_id}")
async def cancel_reservation(request: Request, reservation_id: int) -> JSONResponse:
    """Annule une rÃ©servation."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Non autorisÃ©")
    
    conn = get_db_connection()
    
    # VÃ©rifier que l'utilisateur est propriÃ©taire de la rÃ©servation
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM reservations WHERE id = %s", (reservation_id,))
        reservation = cur.fetchone()
    else:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM reservations WHERE id = ?", (reservation_id,))
        reservation = cur.fetchone()
    
    if not reservation:
        raise HTTPException(status_code=404, detail="RÃ©servation introuvable")
    
    reservation_user_id = reservation[0] if hasattr(conn, '_is_mysql') and conn._is_mysql else reservation['user_id']
    
    if reservation_user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="AccÃ¨s non autorisÃ©")
    
    # Supprimer la rÃ©servation
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur.execute("DELETE FROM reservations WHERE id = %s", (reservation_id,))
    else:
        cur.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    
    conn.commit()
    conn.close()
    
    return JSONResponse({"success": True, "message": "RÃ©servation annulÃ©e"})


@app.get("/reservations/calendar")
async def get_calendar_data(request: Request) -> JSONResponse:
    """Retourne les donnÃ©es du calendrier pour l'API."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Non autorisÃ©")
    
    start_date = request.query_params.get("start")
    end_date = request.query_params.get("end")
    
    conn = get_db_connection()
    
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        cur.execute(
            "SELECT r.*, u.full_name FROM reservations r JOIN users u ON r.user_id = u.id "
            "WHERE date BETWEEN %s AND %s",
            (start_date, end_date)
        )
        reservations = cur.fetchall()
    else:
        cur = conn.cursor()
        cur.execute(
            "SELECT r.*, u.full_name FROM reservations r JOIN users u ON r.user_id = u.id "
            "WHERE date BETWEEN ? AND ?",
            (start_date, end_date)
        )
        reservations = cur.fetchall()
    
    conn.close()
    
    # Formater les donnÃ©es pour le calendrier
    calendar_events = []
    for res in reservations:
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            event = {
                "id": res[0],
                "title": f"Court {res[2]} - {res[5]}",
                "start": f"{res[3]}T{res[4]}:00",
                "end": f"{res[3]}T{res[5]}:00",
                "backgroundColor": "#007bff" if res[1] == user.id else "#6c757d"
            }
        else:
            event = {
                "id": res['id'],
                "title": f"Court {res['court_number']} - {res['full_name']}",
                "start": f"{res['date']}T{res['start_time']}:00",
                "end": f"{res['date']}T{res['end_time']}:00",
                "backgroundColor": "#007bff" if res['user_id'] == user.id else "#6c757d"
            }
        calendar_events.append(event)
    
    return JSONResponse(calendar_events)


@app.get("/reservations/notifications")
async def get_notifications(request: Request) -> JSONResponse:
    """Retourne les notifications de l'utilisateur."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Non autorisÃ©")
    
    conn = get_db_connection()
    
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC LIMIT 10",
            (user.id,)
        )
        notifications = cur.fetchall()
    else:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
            (user.id,)
        )
        notifications = cur.fetchall()
    
    conn.close()
    
    return JSONResponse({"notifications": notifications})


@app.post("/reservations/favorites")
async def add_favorite_slot(request: Request) -> JSONResponse:
    """Ajoute un crÃ©neau favori."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Non autorisÃ©")
    
    form = await request.form()
    court_number = int(form.get("court_number"))
    start_time = form.get("start_time")
    end_time = form.get("end_time")
    day_of_week = form.get("day_of_week")
    
    conn = get_db_connection()
    
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO favorite_slots (user_id, court_number, start_time, end_time, day_of_week) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user.id, court_number, start_time, end_time, day_of_week)
        )
    else:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO favorite_slots (user_id, court_number, start_time, end_time, day_of_week) "
            "VALUES (?, ?, ?, ?, ?)",
            (user.id, court_number, start_time, end_time, day_of_week)
        )
    
    conn.commit()
    conn.close()
    
    return JSONResponse({"success": True, "message": "CrÃ©neau favori ajoutÃ©"})


@app.get("/reservations/stats")
async def get_user_stats(request: Request) -> JSONResponse:
    """Retourne les statistiques de l'utilisateur."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Non autorisÃ©")
    
    conn = get_db_connection()
    
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        # Statistiques gÃ©nÃ©rales
        cur.execute(
            "SELECT COUNT(*) as total, COUNT(DISTINCT date) as days, "
            "COUNT(DISTINCT court_number) as courts FROM reservations WHERE user_id = %s",
            (user.id,)
        )
        general_stats = cur.fetchone()
        
        # Statistiques par mois
        cur.execute(
            "SELECT DATE_FORMAT(date, '%%Y-%%m') as month, COUNT(*) as count "
            "FROM reservations WHERE user_id = %s GROUP BY month ORDER BY month DESC LIMIT 12",
            (user.id,)
        )
        monthly_stats = cur.fetchall()
        
        # Court prÃ©fÃ©rÃ©
        cur.execute(
            "SELECT court_number, COUNT(*) as count FROM reservations WHERE user_id = %s "
            "GROUP BY court_number ORDER BY count DESC LIMIT 1",
            (user.id,)
        )
        favorite_court = cur.fetchone()
        
    else:
        cur = conn.cursor()
        # Statistiques gÃ©nÃ©rales
        cur.execute(
            "SELECT COUNT(*) as total, COUNT(DISTINCT date) as days, "
            "COUNT(DISTINCT court_number) as courts FROM reservations WHERE user_id = ?",
            (user.id,)
        )
        general_stats = cur.fetchone()
        
        # Statistiques par mois
        cur.execute(
            "SELECT strftime('%Y-%m', date) as month, COUNT(*) as count "
            "FROM reservations WHERE user_id = ? GROUP BY month DESC LIMIT 12",
            (user.id,)
        )
        monthly_stats = cur.fetchall()
        
        # Court prÃ©fÃ©rÃ©
        cur.execute(
            "SELECT court_number, COUNT(*) as count FROM reservations WHERE user_id = ? "
            "GROUP BY court_number ORDER BY count DESC LIMIT 1",
            (user.id,)
        )
        favorite_court = cur.fetchone()
    
    conn.close()
    
    stats = {
        "total_reservations": general_stats[0] if hasattr(conn, '_is_mysql') and conn._is_mysql else general_stats['total'],
        "days_played": general_stats[1] if hasattr(conn, '_is_mysql') and conn._is_mysql else general_stats['days'],
        "courts_used": general_stats[2] if hasattr(conn, '_is_mysql') and conn._is_mysql else general_stats['courts'],
        "monthly_stats": monthly_stats,
        "favorite_court": favorite_court[0] if favorite_court else None
    }
    
    return JSONResponse(stats)


@app.get("/admin/membres", response_class=HTMLResponse)
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


@app.get("/admin/membres/ajouter", response_class=HTMLResponse)
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


@app.post("/admin/membres/ajouter", response_class=HTMLResponse)
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


@app.post("/admin/membres/valider", response_class=HTMLResponse)
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


@app.post("/admin/membres/supprimer", response_class=HTMLResponse)
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


@app.post("/admin/membres/supprimer-groupe", response_class=HTMLResponse)
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


@app.get("/admin/membres/{member_id}/details")
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


@app.get("/admin/membres/{member_id}/edit", response_class=HTMLResponse)
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


@app.post("/admin/membres/{member_id}/edit", response_class=HTMLResponse)
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


@app.get("/admin/reservations", response_class=HTMLResponse)
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


@app.post("/admin/reservations/supprimer", response_class=HTMLResponse)
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


@app.post("/admin/reservations/supprimer-lot", response_class=HTMLResponse)
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


@app.post("/admin/reservations/annuler-lot", response_class=HTMLResponse)
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


@app.get("/admin/reservations/export")
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


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse:
    """Gestion personnalisÃ©e des exceptions HTTP pour les redirections.

    Permet de renvoyer des redirections Ã  partir d'une HTTPException avec le
    code 302 et un champ `detail` indiquant l'URL cible.
    """
    # Si le code est 302, on redirige plutÃ´t que d'afficher l'erreur
    if exc.status_code == 302 and exc.detail:
        return RedirectResponse(url=exc.detail, status_code=exc.status_code)
    # Sinon, on renvoie une page d'erreur gÃ©nÃ©rique
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": exc.status_code, "detail": exc.detail},
        status_code=exc.status_code,
    )

# -----------------------------------------------------------------------------
#  Section Articles
# -----------------------------------------------------------------------------

@app.get("/articles", response_class=HTMLResponse)
async def articles_list(request: Request) -> HTMLResponse:
    """Affiche la liste des articles publiÃ©s avec pagination.

    Les articles sont ordonnÃ©s par date de crÃ©ation dÃ©croissante. Chaque entrÃ©e
    prÃ©sente le titre, une image s'il y en a une et un extrait du contenu.

    Args:
        request: objet Request pour rÃ©cupÃ©rer la session et les URLs.

    Returns:
        Page HTML contenant la liste des articles.
    """
    try:
        # RÃ©cupÃ©ration des paramÃ¨tres de pagination
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 6))  # 6 articles par page
        
        # Calcul des offsets
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            
            # Compter le nombre total d'articles
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM articles")
            total_articles = cur.fetchone()[0]
        
            # RÃ©cupÃ©rer les articles pour la page courante
            cur, column_names = execute_with_names("""
                SELECT id, title, content, image_path, created_at, 
                       COALESCE(image_path, '') as image_path_clean
                FROM articles 
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            articles = cur.fetchall()
            # Convertir les tuples MySQL en objets avec attributs nommÃ©s
            articles = [convert_mysql_result(article, column_names) for article in articles]
        else:
            cur = conn.cursor()
            
            # Compter le nombre total d'articles
            cur.execute("SELECT COUNT(*) FROM articles")
            total_articles = cur.fetchone()[0]
            
            # RÃ©cupÃ©rer les articles pour la page courante
            cur.execute("""
                SELECT id, title, content, image_path, created_at, 
                       COALESCE(image_path, '') as image_path_clean
                FROM articles 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (per_page, offset))
            articles = cur.fetchall()
        
        conn.close()
        user = get_current_user(request)
        
        # Calcul de la pagination
        total_pages = max(1, (total_articles + per_page - 1) // per_page)
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
                    'url': f"/articles?page={p}&per_page={per_page}"
                })
        
        return templates.TemplateResponse(
            "articles.html",
            {
                "request": request,
                "user": user,
                "articles": articles,
                "pagination": {
                    "current_page": page,
                    "total_pages": total_pages,
                    "total_articles": total_articles,
                    "per_page": per_page,
                    "has_prev": has_prev,
                    "has_next": has_next,
                    "prev_url": f"/articles?page={page-1}&per_page={per_page}" if has_prev else None,
                    "next_url": f"/articles?page={page+1}&per_page={per_page}" if has_next else None,
                    "links": pagination_links
                },
            },
        )
        
    except Exception as e:
        print(f"âŒ Erreur lors de la rÃ©cupÃ©ration des articles: {e}")
        # En cas d'erreur, retourner une page avec message d'erreur
        user = get_current_user(request)
        return templates.TemplateResponse(
            "articles.html",
            {
                "request": request,
                "user": user,
                "articles": [],
                "error": f"Erreur lors du chargement des articles: {str(e)}"
            },
        )


@app.get("/articles/{article_id}", response_class=HTMLResponse)
async def article_detail(request: Request, article_id: int) -> HTMLResponse:
    """Affiche le dÃ©tail d'un article de presse.

    Args:
        request: objet Request.
        article_id: identifiant de l'article Ã  afficher.

    Returns:
        Page HTML avec le contenu de l'article ou page d'erreur si introuvable.
    """
    try:
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            cur, column_names = execute_with_names("SELECT id, title, content, image_path, created_at FROM articles WHERE id = %s", (article_id,))
            article = cur.fetchone()
            # Convertir le tuple MySQL en objet avec attributs nommÃ©s
            if article:
                article = convert_mysql_result(article, column_names)
        else:
            cur = conn.cursor()
            cur.execute("SELECT id, title, content, image_path, created_at FROM articles WHERE id = ?", (article_id,))
            article = cur.fetchone()
        
        if article is None:
            conn.close()
            raise HTTPException(status_code=404, detail="Article introuvable")
            
        user = get_current_user(request)
        # Construire une URL absolue pour le partage sur Facebook. Si l'application est
        # hÃ©bergÃ©e derriÃ¨re un proxy, request.url donnera l'URL complÃ¨te.
        article_url = str(request.url)
            
        # RÃ©cupÃ©rer les articles rÃ©cents pour la sidebar (avant de fermer la connexion)
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            cur, column_names = execute_with_names(
                "SELECT id, title, content, image_path, created_at FROM articles WHERE id != %s ORDER BY created_at DESC LIMIT 5", 
                (article_id,)
            )
            recent_articles = cur.fetchall()
            # Convertir les tuples MySQL en objets avec attributs nommÃ©s
            recent_articles = [convert_mysql_result(article, column_names) for article in recent_articles]
        else:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, title, content, image_path, created_at FROM articles WHERE id != ? ORDER BY created_at DESC LIMIT 5", 
                (article_id,)
            )
            recent_articles = cur.fetchall()
        
        # Fermer la connexion aprÃ¨s avoir rÃ©cupÃ©rÃ© tous les donnÃ©es
        conn.close()
        
        return templates.TemplateResponse(
            "article_detail.html",
            {
                "request": request,
                "user": user,
                "article": article,
                "recent_articles": recent_articles,
                "share_url": f"https://www.facebook.com/sharer/sharer.php?u={urllib.parse.quote(article_url, safe='')}",
            },
        )
    except Exception as e:
        print(f"âŒ Erreur dans article_detail: {e}")
        # En cas d'erreur, retourner une page d'erreur
        user = get_current_user(request)
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "status_code": 500,
                "detail": f"Erreur lors du chargement de l'article: {str(e)}"
            },
            status_code=500
        )


@app.get("/admin/articles", response_class=HTMLResponse)
async def admin_articles(request: Request) -> HTMLResponse:
    """Interface d'administration des articles.

    Permet aux administrateurs de voir la liste des articles et de crÃ©er de
    nouveaux articles. Les administrateurs peuvent supprimer les articles
    existants via cette interface.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    conn = get_db_connection()
    
    # VÃ©rifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        from database import get_mysql_cursor_with_names, convert_mysql_result
        execute_with_names = get_mysql_cursor_with_names(conn)
        cur, column_names = execute_with_names("SELECT id, title, created_at FROM articles ORDER BY created_at DESC")
        articles = cur.fetchall()
        # Convertir les tuples MySQL en objets avec attributs nommÃ©s
        articles = [convert_mysql_result(article, column_names) for article in articles]
    else:
        cur = conn.cursor()
        cur.execute("SELECT id, title, created_at FROM articles ORDER BY datetime(created_at) DESC")
        articles = cur.fetchall()
    conn.close()
    return templates.TemplateResponse(
        "admin_articles.html",
        {
            "request": request,
            "user": user,
            "articles": articles,
        },
    )


@app.get("/admin/articles/nouveau", response_class=HTMLResponse)
async def admin_new_article_form(request: Request) -> HTMLResponse:
    """Affiche le formulaire de crÃ©ation d'un nouvel article pour les administrateurs."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    return templates.TemplateResponse(
        "admin_article_form.html",
        {"request": request, "user": user, "errors": []},
    )


@app.post("/admin/articles/nouveau", response_class=HTMLResponse)
async def admin_new_article(request: Request) -> HTMLResponse:
    """Traite la soumission du formulaire de crÃ©ation d'article.

    Ce gestionnaire prend en charge deux types de formulaires :
    - `multipart/form-data` : permet de tÃ©lÃ©charger un fichier image depuis le
      navigateur grÃ¢ce Ã  un champ `<input type="file" name="image_file">`. Le
      fichier est enregistrÃ© dans `static/article_images/` avec un nom unique.
    - `application/x-www-form-urlencoded` : permet de spÃ©cifier un champ
      `image_url` contenant l'adresse de l'image.

    Dans tous les cas, le titre et le contenu sont requis. Si un champ est
    manquant, une erreur est renvoyÃ©e et le formulaire est rÃ©affichÃ©.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    # DÃ©terminer le type de contenu
    content_type = request.headers.get("content-type", "")
    errors: List[str] = []
    title = ""
    content_text = ""
    image_path: str = ""
    
    # Lire le body une seule fois
    body = await request.body()
    
    if "multipart/form-data" in content_type:
        # Analyse du corps multipart
        form = parse_multipart_form(body, content_type)
        title = str(form.get("title", "")).strip()
        content_text = str(form.get("content", "")).strip()
        
        # Gestion du fichier image s'il existe
        file_field = form.get("image_file")
        if file_field and isinstance(file_field, dict):
            filename = file_field.get("filename")
            file_content = file_field.get("content", b"")
            if filename and file_content:
                # GÃ©nÃ©rer un nom unique pour Ã©viter les collisions
                ext = os.path.splitext(filename)[1] or ".bin"
                unique_name = f"{uuid.uuid4().hex}{ext}"
                
                # Upload vers HostGator exclusivement
                try:
                    result = upload_photo_to_imgbb(file_content, unique_name)
                    if result.get('success'):
                        # Utiliser l'URL complÃ¨te ImgBB pour la base de donnÃ©es
                        image_path = result.get('url')
                        print(f"âœ… Image uploadÃ©e vers ImgBB: {image_path}")
                    else:
                        # En cas d'Ã©chec, utiliser l'image par dÃ©faut ImgBB
                        image_path = "https://i.ibb.co/8nBCWmhf/test-image-png.png"
                        print(f"âš ï¸ Ã‰chec upload ImgBB, utilisation image par dÃ©faut: {result.get('error')}")
                except Exception as e:
                    # En cas d'erreur, utiliser l'image par dÃ©faut ImgBB
                    image_path = "https://i.ibb.co/8nBCWmhf/test-image-png.png"
                    print(f"âŒ Erreur HostGator, utilisation image par dÃ©faut: {e}")
    else:
        # Analyse du corps form-urlencoded
        form = urllib.parse.parse_qs(body.decode(), keep_blank_values=True)
        title = form.get("title", [""])[0].strip()
        content_text = form.get("content", [""])[0].strip()
        image_path = form.get("image_url", [""])[0].strip()
    
    # VÃ©rifications
    if not title:
        errors.append("Le titre est obligatoire.")
    if not content_text:
        errors.append("Le contenu est obligatoire.")
    
    # Si erreurs, renvoyer le formulaire avec les champs saisis
    if errors:
        return templates.TemplateResponse(
            "admin_article_form.html",
            {
                "request": request,
                "user": user,
                "errors": errors,
                "title": title,
                "content": content_text,
                # Si le formulaire multipart a Ã©tÃ© utilisÃ©, l'URL n'est pas disponible
                "image_url": image_path if "multipart/form-data" not in content_type else "",
            },
        )
    
    # InsÃ©rer dans la base de donnÃ©es
    conn = get_db_connection()
    
    # VÃ©rifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        now_str = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO articles (title, content, image_path, created_at) VALUES (%s, %s, %s, %s)",
            (title, content_text, image_path, now_str),
        )
    else:
        cur = conn.cursor()
        now_str = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO articles (title, content, image_path, created_at) VALUES (?, ?, ?, ?)",
            (title, content_text, image_path, now_str),
        )
    
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/articles", status_code=303)


@app.post("/admin/articles/supprimer", response_class=HTMLResponse)
async def admin_delete_article(request: Request) -> HTMLResponse:
    """Supprime un article de presse (administrateurs uniquement)."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    raw_body = await request.body()
    form = urllib.parse.parse_qs(raw_body.decode(), keep_blank_values=True)
    try:
        article_id = int(form.get("article_id", ["0"])[0])
    except ValueError:
        return RedirectResponse(url="/admin/articles", status_code=303)
    
    conn = get_db_connection()
    
    # RÃ©cupÃ©rer le chemin de l'image avant de supprimer l'article
    image_path = None
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        cur.execute("SELECT image_path FROM articles WHERE id = %s", (article_id,))
        result = cur.fetchone()
        if result:
            image_path = result[0]
    else:
        cur = conn.cursor()
        cur.execute("SELECT image_path FROM articles WHERE id = ?", (article_id,))
        result = cur.fetchone()
        if result:
            image_path = result[0]
    
    # Supprimer l'article de la base de donnÃ©es
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur.execute("DELETE FROM articles WHERE id = %s", (article_id,))
    else:
        cur.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    
    conn.commit()
    conn.close()
    
    # Supprimer le fichier image s'il existe et s'il s'agit d'un upload local
    if image_path and image_path.startswith("/static/article_images/"):
        try:
            # Extraire le nom du fichier du chemin
            filename = os.path.basename(image_path)
            file_path = os.path.join(BASE_DIR, "static", "article_images", filename)
            
            # VÃ©rifier que le fichier existe et le supprimer
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Fichier image supprimÃ© : {file_path}")
        except Exception as e:
            print(f"Erreur lors de la suppression du fichier image : {e}")
    
    return RedirectResponse(url="/admin/articles", status_code=303)


@app.post("/admin/articles/nettoyer-images", response_class=HTMLResponse)
async def admin_cleanup_orphaned_images(request: Request) -> HTMLResponse:
    """Nettoie les images orphelines (images sans article associÃ©)."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    conn = get_db_connection()
    
    # RÃ©cupÃ©rer tous les chemins d'images utilisÃ©s dans la base
    used_images = set()
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        cur.execute("SELECT image_path FROM articles WHERE image_path IS NOT NULL AND image_path != ''")
        results = cur.fetchall()
        for result in results:
            if result[0]:
                used_images.add(result[0])
    else:
        cur = conn.cursor()
        cur.execute("SELECT image_path FROM articles WHERE image_path IS NOT NULL AND image_path != ''")
        results = cur.fetchall()
        for result in results:
            if result[0]:
                used_images.add(result[0])
    
    conn.close()
    
    # Parcourir le dossier des images et supprimer les orphelines
    images_dir = os.path.join(BASE_DIR, "static", "article_images")
    cleaned_count = 0
    
    if os.path.exists(images_dir):
        for filename in os.listdir(images_dir):
            if filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                image_path = f"/static/article_images/{filename}"
                if image_path not in used_images:
                    try:
                        file_path = os.path.join(images_dir, filename)
                        os.remove(file_path)
                        cleaned_count += 1
                        print(f"Image orpheline supprimÃ©e : {filename}")
                    except Exception as e:
                        print(f"Erreur lors de la suppression de {filename}: {e}")
    
    # Rediriger avec un message de succÃ¨s
    return RedirectResponse(
        url=f"/admin/articles?cleaned={cleaned_count}", 
        status_code=303
    )


@app.get("/admin/articles/modifier/{article_id}", response_class=HTMLResponse)
async def admin_edit_article_form(request: Request, article_id: int) -> HTMLResponse:
    """Affiche le formulaire de modification d'un article pour les administrateurs."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    conn = get_db_connection()
    
    # VÃ©rifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        from database import get_mysql_cursor_with_names, convert_mysql_result
        execute_with_names = get_mysql_cursor_with_names(conn)
        cur, column_names = execute_with_names("SELECT id, title, content, image_path, created_at FROM articles WHERE id = %s", (article_id,))
        article = cur.fetchone()
        # Convertir le tuple MySQL en objet avec attributs nommÃ©s
        article = convert_mysql_result(article, column_names) if article else None
    else:
        cur = conn.cursor()
        cur.execute("SELECT id, title, content, image_path, created_at FROM articles WHERE id = ?", (article_id,))
        article = cur.fetchone()
    
    conn.close()
    
    if not article:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "Article introuvable."},
        )
    
    return templates.TemplateResponse(
        "admin_edit_article.html",
        {"request": request, "user": user, "article": article, "errors": []},
    )


@app.post("/admin/articles/modifier/{article_id}", response_class=HTMLResponse)
async def admin_edit_article(request: Request, article_id: int) -> HTMLResponse:
    """Traite la soumission du formulaire de modification d'article."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    # DÃ©terminer le type de contenu
    content_type = request.headers.get("content-type", "")
    errors: List[str] = []
    title = ""
    content_text = ""
    image_path: str = ""
    
    if "multipart/form-data" in content_type:
        # Analyse du corps multipart
        body = await request.body()
        form = parse_multipart_form(body, content_type)
        title = str(form.get("title", "")).strip()
        content_text = str(form.get("content", "")).strip()
        # Gestion du fichier image s'il existe
        file_field = form.get("image_file")
        if file_field and isinstance(file_field, dict):
            filename = file_field.get("filename")
            file_content = file_field.get("content", b"")
            if filename and file_content:
                # CrÃ©er un dossier pour les images si nÃ©cessaire
                images_dir = os.path.join(BASE_DIR, "static", "article_images")
                os.makedirs(images_dir, exist_ok=True)
                # GÃ©nÃ©rer un nom unique pour Ã©viter les collisions
                ext = os.path.splitext(filename)[1] or ".bin"
                unique_name = f"{uuid.uuid4().hex}{ext}"
                # Upload vers ImgBB exclusivement
                try:
                    result = upload_photo_to_imgbb(file_content, unique_name)
                    if result.get('success'):
                        image_path = result.get('url')
                        print(f"âœ… Image uploadÃ©e vers ImgBB: {image_path}")
                    else:
                        # En cas d'Ã©chec, utiliser l'image par dÃ©faut ImgBB
                        image_path = "https://i.ibb.co/8nBCWmhf/test-image-png.png"
                        print(f"âš ï¸ Ã‰chec upload ImgBB, utilisation image par dÃ©faut: {result.get('error')}")
                except Exception as e:
                    # En cas d'erreur, utiliser l'image par dÃ©faut ImgBB
                    image_path = "https://i.ibb.co/8nBCWmhf/test-image-png.png"
                    print(f"âŒ Erreur HostGator, utilisation image par dÃ©faut: {e}")
    else:
        # Formulaire standard urlencoded (image_url fourni par l'utilisateur)
        raw_body = await request.body()
        form = urllib.parse.parse_qs(raw_body.decode(), keep_blank_values=True)
        title = form.get("title", [""])[0].strip()
        content_text = form.get("content", [""])[0].strip()
        image_path = form.get("image_url", [""])[0].strip()
    
    # VÃ©rifications
    if not title:
        errors.append("Le titre est obligatoire.")
    if not content_text:
        errors.append("Le contenu est obligatoire.")
    
    # Si erreurs, rÃ©cupÃ©rer l'article et renvoyer le formulaire avec les champs saisis
    if errors:
        conn = get_db_connection()
        
        # VÃ©rifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            cur, column_names = execute_with_names("SELECT id, title, content, image_path, created_at FROM articles WHERE id = %s", (article_id,))
            article = cur.fetchone()
            # Convertir le tuple MySQL en objet avec attributs nommÃ©s
            article = convert_mysql_result(article, column_names) if article else None
        else:
            cur = conn.cursor()
            cur.execute("SELECT id, title, content, image_path, created_at FROM articles WHERE id = ?", (article_id,))
            article = cur.fetchone()
        
        conn.close()
        
        if not article:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "message": "Article introuvable."},
            )
        
        # Mettre Ã  jour les valeurs avec celles saisies par l'utilisateur
        article.title = title
        article.content = content_text
        if image_path:
            article.image_path = image_path
        
        return templates.TemplateResponse(
            "admin_edit_article.html",
            {
                "request": request,
                "user": user,
                "article": article,
                "errors": errors,
            },
        )
    
    # Mettre Ã  jour dans la base de donnÃ©es
    conn = get_db_connection()
    
    # VÃ©rifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        if image_path:
            # Si une nouvelle image est fournie, mettre Ã  jour l'image aussi
            cur.execute(
                "UPDATE articles SET title = %s, content = %s, image_path = %s WHERE id = %s",
                (title, content_text, image_path, article_id),
            )
        else:
            # Sinon, garder l'image existante
            cur.execute(
                "UPDATE articles SET title = %s, content = %s WHERE id = %s",
                (title, content_text, article_id),
            )
    else:
        cur = conn.cursor()
        if image_path:
            # Si une nouvelle image est fournie, mettre Ã  jour l'image aussi
            cur.execute(
                "UPDATE articles SET title = ?, content = ?, image_path = ? WHERE id = ?",
                (title, content_text, image_path, article_id),
            )
        else:
            # Sinon, garder l'image existante
            cur.execute(
                "UPDATE articles SET title = ?, content = ? WHERE id = ?",
                (title, content_text, article_id),
            )
    
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/articles", status_code=303)


# -----------------------------------------------------------------------------
#  Espace utilisateur : statistiques de sÃ©ances
# -----------------------------------------------------------------------------

@app.get("/test-espace-simple")
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



@app.get("/test-db-espace")
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

@app.get("/espace", response_class=HTMLResponse)
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

@app.get("/health")
async def health_check():
    """Point de terminaison de santÃ© pour vÃ©rifier l'Ã©tat de l'application et de la base de donnÃ©es."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # VÃ©rifier les tables
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM reservations")
        reservations_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM articles")
        articles_count = cur.fetchone()[0]
        
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


@app.get("/init-articles")
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

@app.get("/init-database")
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
@app.get("/diagnostic-db")
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

@app.get("/debug-auth")
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


@app.get("/fix-admin")
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


@app.get("/restore-backup")
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


@app.get("/test-espace")
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


@app.get("/disable-auto-backup")
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


@app.get("/enable-auto-backup")
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







@app.get("/debug-table-structure")
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

@app.get("/debug-latest-articles")
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

@app.get("/diagnose-database")
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

@app.get("/setup-imgbb")
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

@app.get("/test-db-connection")
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

@app.get("/test-homepage-data")
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

@app.get("/test-imgbb")
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

@app.get("/force-update-all-image-urls")
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








@app.get("/force-cache-refresh")
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

@app.get("/test-template-function")
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

@app.get("/test-html-generation")
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

@app.get("/debug-article-images")
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

@app.get("/fix-production-images")
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

@app.get("/force-disable-backup")
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


@app.get("/check-backup-status")
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



@app.get("/create-admin")
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

@app.get("/backup-database")
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

@app.get("/list-backups")
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

@app.get("/test-admin-reservations")
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

@app.get("/test-espace-simple")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )
