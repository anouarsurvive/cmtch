"""
Application web pour le Club municipal de tennis Chihia.

Ce module définit une application FastAPI simple qui fournit un site web en
langue française pour le club de tennis de Chihia.  Le site comporte un
espace public présentant le club, un formulaire d'inscription pour les
nouveaux membres, un système d'authentification, un espace d'administration
permettant de valider les inscriptions et de gérer les membres, ainsi qu'un
module de réservation pour les trois courts du club.

Pour simplifier le déploiement dans cet environnement, aucune dépendance
externe n'est requise : FastAPI, Starlette et Jinja2 sont déjà fournis.
La base de données utilise SQLite via le module standard `sqlite3`.  Les
sessions sont gérées via le middleware de Starlette qui signe un cookie
contant un identifiant d'utilisateur.

Les mots de passe sont hachés avec SHA‑256.  Une entrée administrateur est
créée automatiquement au démarrage avec le nom d'utilisateur « admin » et
le mot de passe « admin ».  Nous invitons les responsables du club à
changer ces identifiants lors du déploiement.

Autor: ChatGPT
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
# Ajouter le répertoire courant au path pour s'assurer que l'import fonctionne
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from photo_upload_service_imgbb import upload_photo_to_imgbb, test_imgbb_system  # type: ignore
except ImportError as e:
    # Si l'import échoue, créer des fonctions de fallback
    print(f"Attention: Impossible d'importer photo_upload_service_imgbb: {e}")
    def upload_photo_to_imgbb(file_data: bytes, filename: str) -> Dict[str, Any]:
        return {'success': False, 'error': 'Service d\'upload d\'images non disponible'}
    def test_imgbb_system() -> Dict[str, Any]:
        return {'status': 'error', 'message': 'Service d\'upload d\'images non disponible', 'imgbb_working': False}
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

# Middleware pour la gestion des sessions sécurisées
@app.middleware("http")
async def session_middleware(request: Request, call_next):
    """Middleware pour gérer les sessions sécurisées et la régénération des tokens."""
    response = await call_next(request)
    
    # Vérifier si l'utilisateur est connecté
    token = request.cookies.get("session_token")
    if token:
        # Vérifier si le token doit être rafraîchi
        if should_refresh_token(token):
            try:
                # Récupérer l'utilisateur actuel
                user_id = validate_session_token(token)
                if user_id:
                    # Créer un nouveau token
                    ip_address = request.client.host if request.client else None
                    user_agent = request.headers.get("user-agent")
                    new_token = create_secure_session_token(user_id, ip_address, user_agent)
                    
                    # Désactiver l'ancien token
                    deactivate_session(token)
                    
                    # Mettre à jour le cookie
                    response.set_cookie(
                        key="session_token",
                        value=new_token,
                        httponly=True,
                        max_age=60 * 60 * 24 * SESSION_MAX_AGE_DAYS,
                        secure=False,  # Mettre True en production avec HTTPS
                        samesite="lax"
                    )
            except Exception as e:
                print(f"Erreur lors de la régénération du token : {e}")
    
    return response

# Clé secrète pour signer les cookies de session.
SECRET_KEY = "change-me-in-production-please"

# Configuration des sessions sécurisées
SESSION_TIMEOUT_MINUTES = 30  # Timeout d'inactivité
SESSION_MAX_AGE_DAYS = 7      # Durée maximale de la session
SESSION_REFRESH_THRESHOLD = 15 # Minutes avant expiration pour régénérer le token

# Configuration email
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@cmtch.tn")

def detect_language(text: str) -> str:
    """
    Détecte la langue d'un texte (arabe ou français)
    Retourne 'ar' pour l'arabe, 'fr' pour le français
    """
    if not text or not text.strip():
        return 'fr'  # Par défaut français
    
    # Compter les caractères arabes
    arabic_chars = re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', text)
    arabic_count = len(arabic_chars)
    
    # Compter les caractères français/latins
    latin_chars = re.findall(r'[a-zA-Zàâäéèêëïîôöùûüÿçñ]', text)
    latin_count = len(latin_chars)
    
    # Si plus de caractères arabes que latins, c'est de l'arabe
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
# Expose l'objet datetime dans les templates pour afficher l'année dans le pied de page
templates.env.globals["datetime"] = datetime
# Expose les fonctions de détection de langue dans les templates
templates.env.globals["detect_language"] = detect_language
templates.env.globals["get_text_direction"] = get_text_direction
templates.env.globals["get_text_align"] = get_text_align

def ensure_absolute_image_url(image_path: str) -> str:
    """S'assure que l'URL de l'image est absolue (ImgBB ou endpoint)"""
    if not image_path:
        return ""
    
    print(f"🔍 ensure_absolute_image_url: Input = '{image_path}'")
    
    # Si c'est déjà une URL absolue, la retourner telle quelle
    if image_path.startswith(('http://', 'https://')):
        print(f"✅ URL déjà absolue: {image_path}")
        return image_path
    
    # Si c'est une URL relative, la convertir en URL absolue via notre endpoint
    if image_path.startswith('/static/article_images/'):
        filename = image_path.split('/')[-1]
        result = f"https://www.cmtch.online/image/{filename}"
        print(f"🔄 URL relative convertie: {image_path} -> {result}")
        return result
    
    # Si c'est juste le nom du fichier, construire l'URL via notre endpoint
    if not image_path.startswith('/'):
        result = f"https://www.cmtch.online/image/{image_path}"
        print(f"🔄 Nom de fichier converti: {image_path} -> {result}")
        return result
    
    # Par défaut, retourner l'URL telle quelle
    print(f"⚠️ URL non modifiée: {image_path}")
    return image_path

# Expose la fonction dans les templates
templates.env.globals["ensure_absolute_image_url"] = ensure_absolute_image_url

# Test pour vérifier que la fonction est bien exposée
print(f"🔧 Fonction ensure_absolute_image_url exposée: {templates.env.globals.get('ensure_absolute_image_url') is not None}")

# Montage des fichiers statiques (CSS, images, JS)
# Montage StaticFiles pour les fichiers CSS/JS locaux
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)

# Route spécifique pour les images d'articles qui redirige vers HostGator
@app.get("/article_images/{filename}")
async def serve_article_image(filename: str):
    """Redirige les requêtes d'images d'articles vers HostGator"""
    hostgator_url = f"https://www.cmtch.online/static/article_images/{filename}"
    return RedirectResponse(url=hostgator_url, status_code=302)


def create_secure_session_token(user_id: int, ip_address: str = None, user_agent: str = None) -> str:
    """Crée un jeton de session sécurisé et l'enregistre en base de données.

    Args:
        user_id: identifiant numérique de l'utilisateur.
        ip_address: adresse IP de l'utilisateur.
        user_agent: user agent du navigateur.

    Returns:
        Chaîne représentant le jeton de session.
    """
    # Générer un token aléatoire sécurisé
    token = secrets.token_urlsafe(32)
    
    # Calculer les dates d'expiration
    now = datetime.now()
    expires_at = now + timedelta(days=SESSION_MAX_AGE_DAYS)
    
    # Enregistrer la session en base de données
    conn = get_db_connection()
    try:
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO user_sessions (user_id, session_token, expires_at, ip_address, user_agent)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, token, expires_at.isoformat(), ip_address, user_agent))
        else:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO user_sessions (user_id, session_token, expires_at, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, token, expires_at.isoformat(), ip_address, user_agent))
        
        conn.commit()
        return token
    except Exception as e:
        # Si la table user_sessions n'existe pas encore, utiliser l'ancien système
        print(f"⚠️ Table user_sessions manquante, utilisation de l'ancien système: {e}")
        # Retourner un token simple pour l'ancien système
        data = str(user_id).encode()
        signature = hmac.new(SECRET_KEY.encode(), data, hashlib.sha256).hexdigest().encode()
        token_bytes = data + b":" + signature
        return base64.urlsafe_b64encode(token_bytes).decode()
    finally:
        conn.close()


def validate_session_token(token: str, ip_address: str = None) -> Optional[int]:
    """Valide un jeton de session et retourne l'ID utilisateur si valide.

    Args:
        token: Jeton de session à valider.
        ip_address: Adresse IP pour vérification de sécurité.

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
        
        # Vérifier si la session est expirée
        try:
            expires_at = datetime.fromisoformat(str(expires_at_str)) if expires_at_str else datetime.now()
            last_activity = datetime.fromisoformat(str(last_activity_str)) if last_activity_str else datetime.now()
        except (ValueError, TypeError) as e:
            print(f"⚠️ Erreur de parsing de date: {e}")
            return None
        now = datetime.now()
        
        if now > expires_at:
            # Session expirée, la désactiver
            deactivate_session(token)
            return None
        
        # Vérifier le timeout d'inactivité
        if now - last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            # Session inactive trop longtemps, la désactiver
            deactivate_session(token)
            return None
        
        # Vérification optionnelle de l'IP (peut être désactivée pour plus de flexibilité)
        # if ip_address and session_ip and ip_address != session_ip:
        #     return None
        
        # Mettre à jour la dernière activité
        update_session_activity(token)
        
        return user_id
        
    except Exception as e:
        # Si la table user_sessions n'existe pas encore, utiliser l'ancien système
        print(f"⚠️ Table user_sessions manquante, utilisation de l'ancien système: {e}")
        return None
    finally:
        conn.close()


def update_session_activity(token: str) -> None:
    """Met à jour la dernière activité d'une session."""
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
    """Désactive une session."""
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
    """Nettoie les sessions expirées."""
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
    """Vérifie si un token doit être rafraîchi."""
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
            print(f"⚠️ Erreur de parsing de date dans should_refresh_token: {e}")
            return False
        
    except Exception as e:
        # Si la table n'existe pas encore, ne pas rafraîchir
        print(f"⚠️ Erreur lors de la vérification du token (table user_sessions manquante?): {e}")
        return False
    finally:
        conn.close()


# Fonctions de compatibilité avec l'ancien système
def create_session_token(user_id: int) -> str:
    """Fonction de compatibilité - utilise le nouveau système sécurisé."""
    try:
        return create_secure_session_token(user_id)
    except Exception as e:
        # Si le nouveau système échoue, utiliser l'ancien système
        print(f"⚠️ Nouveau système de sessions indisponible, utilisation de l'ancien: {e}")
        data = str(user_id).encode()
        signature = hmac.new(SECRET_KEY.encode(), data, hashlib.sha256).hexdigest().encode()
        token_bytes = data + b":" + signature
        return base64.urlsafe_b64encode(token_bytes).decode()


def parse_session_token(token: Optional[str]) -> Optional[int]:
    """Fonction de compatibilité - utilise le nouveau système sécurisé."""
    if not token:
        return None
    
    # Essayer d'abord l'ancien système (plus fiable pour le fallback)
    try:
        token_bytes = base64.urlsafe_b64decode(token.encode())
        user_id_bytes, signature = token_bytes.split(b":", 1)
        expected_signature = hmac.new(SECRET_KEY.encode(), user_id_bytes, hashlib.sha256).hexdigest().encode()
        if hmac.compare_digest(signature, expected_signature):
            return int(user_id_bytes.decode())
    except Exception:
        pass
    
    # Si l'ancien système échoue, essayer le nouveau système
    user_id = validate_session_token(token)
    if user_id is not None:
        return user_id
    
    return None





def verify_password(password: str, password_hash: str) -> bool:
    """Vérifie qu'un mot de passe correspond à une empreinte enregistrée."""
    from database import hash_password as hash_pwd
    return hash_pwd(password) == password_hash


# Utilitaire pour analyser les formulaires multipart/form-data sans dépendance
def parse_multipart_form(body: bytes, content_type: str) -> Dict[str, Any]:
    """Parse un corps multipart/form-data et retourne un dict des champs.

    Cette fonction analyse les données envoyées dans le corps d'une requête
    multipart/form-data. Les champs simples (texte) sont retournés comme des
    chaînes de caractères. Les champs de fichier sont retournés sous la forme
    d'un dictionnaire avec les clés 'filename' et 'content' (contenu binaire).

    Args:
        body: corps brut de la requête en bytes.
        content_type: valeur de l'en-tête Content-Type (avec le boundary).

    Returns:
        Un dictionnaire où les clés sont les noms de champs.
    """
    result: Dict[str, Any] = {}
    # Extraire le boundary depuis le header
    m = re.search(r"boundary=([^;]+)", content_type)
    if not m:
        return result
    boundary = m.group(1)
    # Les guillemets autour du boundary sont supprimés le cas échéant
    if boundary.startswith('"') and boundary.endswith('"'):
        boundary = boundary[1:-1]
    boundary_bytes = ('--' + boundary).encode()
    parts = body.split(boundary_bytes)
    # On ignore la première et la dernière partie (avant le premier boundary et après le boundary de fermeture)
    for part in parts[1:-1]:
        part = part.strip(b"\r\n")
        if not part:
            continue
        # Séparer les entêtes du contenu
        header_block, _, data = part.partition(b"\r\n\r\n")
        headers: Dict[str, str] = {}
        for header_line in header_block.split(b"\r\n"):
            try:
                key, _, value = header_line.decode(errors="replace").partition(":")
                headers[key.strip().lower()] = value.strip()
            except Exception:
                continue
        content_disp = headers.get('content-disposition', '')
        # Extraire les paramètres du Content-Disposition
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
    """Ouvre une connexion à la base de données (SQLite ou PostgreSQL).

    Returns:
        Instance de connexion à la base de données.
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
        True si l'email a été envoyé avec succès, False sinon
    """
    try:
        if not SMTP_USERNAME or not SMTP_PASSWORD:
            print(f"⚠️ Configuration SMTP manquante - Email non envoyé à {to_email}")
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
        
        print(f"✅ Email envoyé avec succès à {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi d'email à {to_email}: {e}")
        return False


def generate_ics_content(event_title: str, event_description: str, start_datetime: datetime, 
                        end_datetime: datetime, location: str = "Club Municipal de Tennis Chihia") -> str:
    """Génère le contenu d'un fichier ICS (iCalendar).
    
    Args:
        event_title: Titre de l'événement
        event_description: Description de l'événement
        start_datetime: Date et heure de début
        end_datetime: Date et heure de fin
        location: Lieu de l'événement
        
    Returns:
        Contenu du fichier ICS
    """
    # Format des dates pour ICS
    def format_datetime(dt):
        return dt.strftime("%Y%m%dT%H%M%SZ")
    
    # Préparer la description en échappant les caractères spéciaux
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
    """Envoie un email de confirmation de réservation.
    
    Args:
        user_email: Email de l'utilisateur
        user_name: Nom de l'utilisateur
        reservation_data: Données de la réservation
        
    Returns:
        True si l'email a été envoyé avec succès
    """
    subject = f"Confirmation de réservation - Court {reservation_data['court_number']}"
    
    # Contenu texte
    text_content = f"""
Confirmation de réservation - Club Municipal de Tennis Chihia

Bonjour {user_name},

Votre réservation a été confirmée avec succès.

Détails de la réservation :
- Date : {reservation_data['date']}
- Heure : {reservation_data['start_time']} - {reservation_data['end_time']}
- Court : {reservation_data['court_number']}
- ID réservation : #{reservation_data['id']}

Lieu : Club Municipal de Tennis Chihia

Merci de votre confiance !

L'équipe du Club Municipal de Tennis Chihia
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
            <h1>🎾 Confirmation de réservation</h1>
            <p>Club Municipal de Tennis Chihia</p>
        </div>
        <div class="content">
            <p>Bonjour <strong>{user_name}</strong>,</p>
            <p>Votre réservation a été confirmée avec succès !</p>
            
            <div class="reservation-details">
                <h3>📅 Détails de votre réservation</h3>
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
                    <span class="label">ID réservation :</span> #{reservation_data['id']}
                </div>
            </div>
            
            <p><strong>Lieu :</strong> Club Municipal de Tennis Chihia</p>
            
            <p>Merci de votre confiance !</p>
            <p>À bientôt sur les courts ! 🎾</p>
        </div>
        <div class="footer">
            <p>Club Municipal de Tennis Chihia</p>
            <p>Cet email a été envoyé automatiquement, merci de ne pas y répondre.</p>
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
        admin_name: Nom de l'administrateur qui a validé
        
    Returns:
        True si l'email a été envoyé avec succès
    """
    subject = "Votre compte a été validé - Club Municipal de Tennis Chihia"
    
    # Contenu texte
    text_content = f"""
Validation de compte - Club Municipal de Tennis Chihia

Bonjour {user_name},

Excellente nouvelle ! Votre compte a été validé par {admin_name}.

Vous pouvez maintenant :
- Vous connecter à votre espace personnel
- Effectuer des réservations de courts
- Accéder à toutes les fonctionnalités du club

Connectez-vous dès maintenant sur notre site web !

L'équipe du Club Municipal de Tennis Chihia
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
            <h1>✅ Compte validé !</h1>
            <p>Club Municipal de Tennis Chihia</p>
        </div>
        <div class="content">
            <p>Bonjour <strong>{user_name}</strong>,</p>
            <p>Excellente nouvelle ! Votre compte a été validé par <strong>{admin_name}</strong>.</p>
            
            <div class="success-box">
                <h3>🎉 Vous pouvez maintenant :</h3>
                <ul>
                    <li>Vous connecter à votre espace personnel</li>
                    <li>Effectuer des réservations de courts</li>
                    <li>Accéder à toutes les fonctionnalités du club</li>
                </ul>
            </div>
            
            <p style="text-align: center;">
                <a href="https://www.cmtch.online/connexion" class="cta-button">
                    🎾 Se connecter maintenant
                </a>
            </p>
            
            <p>À bientôt sur les courts !</p>
        </div>
        <div class="footer">
            <p>Club Municipal de Tennis Chihia</p>
            <p>Cet email a été envoyé automatiquement, merci de ne pas y répondre.</p>
        </div>
    </div>
</body>
</html>
"""
    
    return send_email(user_email, subject, html_content, text_content)


def hash_password(password: str) -> str:
    """Retourne l'empreinte SHA‑256 d'un mot de passe en clair.

    Args:
        password: Mot de passe en clair.

    Returns:
        Chaîne hexadécimale représentant l'empreinte.
    """
    from database import hash_password as hash_pwd
    return hash_pwd(password)


# SYSTÈME DE SAUVEGARDE AUTOMATIQUE POUR RENDER
# Ce système sauvegarde et restaure automatiquement les données
# pour éviter la perte lors des redémarrages de Render

def backup_database():
    """Crée une sauvegarde de la base de données."""
    try:
        import shutil
        from datetime import datetime
        
        # Créer le dossier de sauvegarde s'il n'existe pas
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        
        # Nom du fichier de sauvegarde avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db"
        backup_path = backup_dir / backup_filename
        
        # Vérifier le type de base de données
        database_url = os.getenv('DATABASE_URL')
        
        if database_url and 'mysql://' in database_url:
            # Pour MySQL, on ne peut pas faire une copie directe du fichier
            # On va exporter les données en SQL
            return backup_mysql_database(backup_path)
        elif database_url:
            # Pour PostgreSQL, on ne peut pas faire une copie directe du fichier
            # On va exporter les données en SQL
            return backup_postgresql_database(backup_path)
        else:
            # Pour SQLite, on peut copier le fichier directement
            source_db = Path("database.db")
            if source_db.exists():
                shutil.copy2(source_db, backup_path)
                print(f"✅ Sauvegarde SQLite créée: {backup_path}")
                return str(backup_path)
            else:
                print("❌ Fichier de base de données SQLite non trouvé")
                return None
                
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        return None

def backup_mysql_database(backup_path):
    """Crée une sauvegarde de la base de données MySQL."""
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
        
        # Connexion à MySQL
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        # Créer le fichier de sauvegarde SQL
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
                
                # Obtenir les données de la table
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
        print(f"✅ Sauvegarde MySQL créée: {sql_backup_path}")
        return sql_backup_path
        
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde MySQL: {e}")
        return None

def backup_postgresql_database(backup_path):
    """Crée une sauvegarde de la base de données PostgreSQL."""
    try:
        import psycopg2
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return None
            
        # Connexion à PostgreSQL
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Créer le fichier de sauvegarde SQL
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
                
                # Obtenir les données de la table
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
        print(f"✅ Sauvegarde PostgreSQL créée: {sql_backup_path}")
        return sql_backup_path
        
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde PostgreSQL: {e}")
        return None

def find_latest_backup():
    """Trouve la sauvegarde la plus récente."""
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
            
        # Retourner le fichier le plus récent
        latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
        return str(latest_backup)
        
    except Exception as e:
        print(f"❌ Erreur lors de la recherche de sauvegarde: {e}")
        return None

def restore_database(backup_path):
    """Restaure la base de données depuis une sauvegarde."""
    try:
        backup_path = Path(backup_path)
        if not backup_path.exists():
            print(f"❌ Fichier de sauvegarde non trouvé: {backup_path}")
            return False
            
        # Vérifier le type de base de données
        database_url = os.getenv('DATABASE_URL')
        
        if database_url and 'mysql://' in database_url:
            return restore_mysql_database(backup_path)
        elif database_url:
            return restore_postgresql_database(backup_path)
        else:
            return restore_sqlite_database(backup_path)
            
    except Exception as e:
        print(f"❌ Erreur lors de la restauration: {e}")
        return False

def restore_sqlite_database(backup_path):
    """Restaure la base de données SQLite depuis une sauvegarde."""
    try:
        import shutil
        
        # Sauvegarder la base actuelle
        current_db = Path("database.db")
        if current_db.exists():
            backup_current = Path("database_backup_before_restore.db")
            shutil.copy2(current_db, backup_current)
            print(f"✅ Sauvegarde de la base actuelle: {backup_current}")
        
        # Restaurer depuis la sauvegarde
        shutil.copy2(backup_path, current_db)
        print(f"✅ Base de données SQLite restaurée depuis: {backup_path}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la restauration SQLite: {e}")
        return False

def restore_mysql_database(backup_path):
    """Restaure la base de données MySQL depuis une sauvegarde."""
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
        
        # Connexion à MySQL
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        # Lire et exécuter le fichier SQL
        with open(backup_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
            
        cursor = conn.cursor()
        
        # Exécuter les commandes SQL une par une
        for statement in sql_content.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                except Exception as e:
                    print(f"⚠️ Erreur lors de l'exécution de: {statement[:50]}... - {e}")
        
        conn.commit()
        conn.close()
        print(f"✅ Base de données MySQL restaurée depuis: {backup_path}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la restauration MySQL: {e}")
        return False

def restore_postgresql_database(backup_path):
    """Restaure la base de données PostgreSQL depuis une sauvegarde."""
    try:
        import psycopg2
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return False
            
        # Connexion à PostgreSQL
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Lire et exécuter le fichier SQL
        with open(backup_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
            
        # Exécuter les commandes SQL une par une
        for statement in sql_content.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                except Exception as e:
                    print(f"⚠️ Erreur lors de l'exécution de: {statement[:50]}... - {e}")
        
        conn.commit()
        conn.close()
        print(f"✅ Base de données PostgreSQL restaurée depuis: {backup_path}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la restauration PostgreSQL: {e}")
        return False

def auto_backup_system():
    """Système de sauvegarde automatique pour préserver les données sur Render."""
    try:
        print("🔄 Démarrage du système de sauvegarde automatique...")
        
        # Vérifier si le système est désactivé
        flag_file = Path("DISABLE_AUTO_BACKUP")
        if flag_file.exists():
            print("🚫 Système de sauvegarde automatique désactivé par l'utilisateur")
            return
        
        # Vérifier si on est sur Render (présence de DATABASE_URL)
        if not os.getenv('DATABASE_URL'):
            print("ℹ️ Pas sur Render - système de sauvegarde ignoré")
            return
        
        # Vérifier d'abord si la base de données contient des données
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Vérifier si la table users existe et contient des données
            cur.execute("SELECT COUNT(*) FROM users")
            users_count = cur.fetchone()[0]
            
            if users_count > 0:
                print(f"✅ Base de données contient {users_count} utilisateur(s) - Sauvegarde uniquement")
                # Si des données existent, faire seulement une sauvegarde
                backup_file = backup_database()
                if backup_file:
                    print(f"✅ Sauvegarde créée: {backup_file}")
                else:
                    print("⚠️ Échec de la sauvegarde")
            else:
                print("📭 Base de données vide - Tentative de restauration")
                # Si la base est vide, essayer de restaurer
                latest_backup = find_latest_backup()
                if latest_backup:
                    print(f"🔄 Restauration depuis {latest_backup}")
                    if restore_database(latest_backup):
                        print("✅ Restauration réussie")
                    else:
                        print("❌ Échec de la restauration")
                else:
                    print("📭 Aucune sauvegarde trouvée")
                    
        except Exception as e:
            print(f"❌ Erreur lors de la vérification de la base: {e}")
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Erreur dans le système de sauvegarde automatique: {e}")

#
# Si vous voulez l'activer, utilisez l'endpoint /enable-auto-backup
# Si vous voulez le désactiver, utilisez l'endpoint /disable-auto-backup
#
# auto_backup_system()


def get_current_user(request: Request) -> Optional[sqlite3.Row]:
    """Retourne l'utilisateur actuellement connecté à partir du cookie de session.

    Args:
        request: L'objet Request en cours.

    Returns:
        Une ligne représentant l'utilisateur, ou None si aucun utilisateur
        n'est authentifié.
    """
    token = request.cookies.get("session_token")
    if not token:
        return None
    
    # Récupérer l'IP et user agent pour la validation
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # Valider le token avec le nouveau système sécurisé
    user_id = validate_session_token(token, ip_address)
    if not user_id:
        return None
    
    # Récupérer les informations de l'utilisateur
    conn = get_db_connection()
    try:
        # Vérifier si c'est une connexion MySQL
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
    """Décorateur simple pour s'assurer qu'un utilisateur est connecté.

    Si aucun utilisateur n'est connecté, redirige vers la page de connexion.

    Args:
        request: L'objet Request en cours.

    Returns:
        La ligne représentant l'utilisateur connecté.
    """
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=302, detail="Not authenticated")
    return user


@app.on_event("startup")
async def startup() -> None:
    """Appelé au démarrage de l'application."""
    print("🚀 Démarrage de l'application...")
    
    # IMPORTANT : AUCUNE initialisation automatique de la base de données
    # Les tables et données existantes doivent être préservées
    print("ℹ️ Initialisation automatique de la base de données désactivée")
    print("ℹ️ Les données existantes sont préservées")
    
    # Vérifier seulement la connexion à la base
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Compter les données existantes
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM articles")
        articles_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM reservations")
        reservations_count = cur.fetchone()[0]
        
        print(f"📊 État de la base de données au démarrage :")
        print(f"   - Utilisateurs : {users_count}")
        print(f"   - Articles : {articles_count}")
        print(f"   - Réservations : {reservations_count}")
        
        conn.close()
        
    except Exception as e:
        print(f"⚠️ Impossible de vérifier l'état de la base : {e}")
    
    # Nettoyer les sessions expirées au démarrage
    try:
        cleanup_expired_sessions()
        print("✅ Nettoyage des sessions expirées effectué")
    except Exception as e:
        print(f"⚠️ Erreur lors du nettoyage des sessions : {e}")
    
    print("🎉 Application prête !")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """Page d'accueil du site.

    Affiche une présentation du club, les coordonnées et un lien vers les
    différentes sections selon le rôle de l'utilisateur.
    """
    user = get_current_user(request)
    # Informations publiques sur le club provenant de sources fiables.
    adresse = "Route Teboulbi km 6, 3041 Sfax sud"
    telephone = "+216 29 60 03 40"
    email = "club.tennis.chihia@gmail.com"
    description = (
        "Club municipal de tennis Chihia est un lieu spécialement conçu pour les personnes "
        "souhaitant pratiquer le Tennis."
    )
    # Récupérer les trois derniers articles pour les mettre en avant sur l'accueil
    conn = get_db_connection()
    
    # Vérifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        from database import get_mysql_cursor_with_names, convert_mysql_result
        execute_with_names = get_mysql_cursor_with_names(conn)
        cur, column_names = execute_with_names(
            "SELECT id, title, content, image_path, created_at FROM articles ORDER BY created_at DESC LIMIT 3"
        )
        latest_articles = cur.fetchall()
        # Convertir les tuples MySQL en objets avec attributs nommés
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
    # Si un utilisateur est déjà connecté, on le redirige vers l'accueil
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "register.html",
        {"request": request},
    )


@app.post("/inscription", response_class=HTMLResponse)
async def register(request: Request) -> HTMLResponse:
    """Traite la soumission du formulaire d'inscription.

    Si le nom d'utilisateur est déjà pris ou si les mots de passe ne
    correspondent pas, la page renvoie un message d'erreur.
    L'utilisateur est créé avec l'attribut `validated` à 0 et ne pourra pas se
    connecter tant qu'un administrateur ne l'aura pas validé.
    """
    try:
        # Utiliser Form pour une gestion plus robuste des données
        form_data = await request.form()
        
        # Récupération des données du formulaire
        username = str(form_data.get("username", "")).strip()
        full_name = str(form_data.get("full_name", "")).strip()
        email = str(form_data.get("email", "")).strip()
        phone = str(form_data.get("phone", "")).strip()
        ijin_number = str(form_data.get("ijin_number", "")).strip()
        birth_date = str(form_data.get("birth_date", "")).strip()
        password = str(form_data.get("password", ""))
        confirm_password = str(form_data.get("confirm_password", ""))
        role = str(form_data.get("role", "member"))
        
        # Vérifications de base
        errors: List[str] = []
        
        if not username:
            errors.append("Le nom d'utilisateur est obligatoire.")
        if not full_name:
            errors.append("Le nom complet est obligatoire.")
        if not email:
            errors.append("L'adresse e‑mail est obligatoire.")
        if not phone:
            errors.append("Le téléphone est obligatoire.")
        # Le numéro IJIN n'est plus obligatoire
        # if not ijin_number:
        #     errors.append("Le numéro IJIN est obligatoire.")
        if not birth_date:
            errors.append("La date de naissance est obligatoire.")
        if not password:
            errors.append("Le mot de passe est obligatoire.")
        if password != confirm_password:
            errors.append("Les mots de passe ne correspondent pas.")
        if len(password) < 6:
            errors.append("Le mot de passe doit contenir au moins 6 caractères.")
            
        # Vérifier que le nom d'utilisateur, l'email et le téléphone n'existent pas déjà
        conn = get_db_connection()
        
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            # Vérifier le nom d'utilisateur
            cur.execute("SELECT id, username FROM users WHERE username = %s", (username,))
            existing_user = cur.fetchone()
            if existing_user:
                errors.append("Ce nom d'utilisateur est déjà utilisé.")
            
            # Vérifier l'email
            cur.execute("SELECT id, username, email FROM users WHERE email = %s", (email,))
            existing_email = cur.fetchone()
            if existing_email:
                errors.append(f"Cette adresse email ({email}) est déjà utilisée par l'utilisateur '{existing_email[1]}'. Si c'est votre compte, vous pouvez récupérer votre mot de passe.")
            
            # Vérifier le téléphone
            cur.execute("SELECT id, username, phone FROM users WHERE phone = %s", (phone,))
            existing_phone = cur.fetchone()
            if existing_phone:
                errors.append(f"Ce numéro de téléphone ({phone}) est déjà utilisé par l'utilisateur '{existing_phone[1]}'. Si c'est votre compte, vous pouvez récupérer votre mot de passe.")
        else:
            cur = conn.cursor()
            # Vérifier le nom d'utilisateur
            cur.execute("SELECT id, username FROM users WHERE username = ?", (username,))
            existing_user = cur.fetchone()
            if existing_user:
                errors.append("Ce nom d'utilisateur est déjà utilisé.")
            
            # Vérifier l'email
            cur.execute("SELECT id, username, email FROM users WHERE email = ?", (email,))
            existing_email = cur.fetchone()
            if existing_email:
                errors.append(f"Cette adresse email ({email}) est déjà utilisée par l'utilisateur '{existing_email[1]}'. Si c'est votre compte, vous pouvez récupérer votre mot de passe.")
            
            # Vérifier le téléphone
            cur.execute("SELECT id, username, phone FROM users WHERE phone = ?", (phone,))
            existing_phone = cur.fetchone()
            if existing_phone:
                errors.append(f"Ce numéro de téléphone ({phone}) est déjà utilisé par l'utilisateur '{existing_phone[1]}'. Si c'est votre compte, vous pouvez récupérer votre mot de passe.")
            
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
            
        # Création de l'utilisateur
        pwd_hash = hash_password(password)
        is_trainer = 1 if role == "trainer" else 0
        
        # Vérification email désactivée - marquer directement comme vérifié
        email_verification_token = None
        email_verified = 1
        
        # Vérifier si c'est une connexion MySQL
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
        
        print(f"✅ Utilisateur créé avec succès: {username}")
        
        # Vérification email désactivée - redirection simple
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
        print(f"❌ Erreur lors de l'inscription: {e}")
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
        
        # Vérifier si c'est une connexion MySQL
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
                    "error": "Token de validation invalide ou expiré."
                }
            )
        
        user_id, username, email, email_verified = user
        
        if email_verified:
            conn.close()
            return templates.TemplateResponse(
                "email_verification_error.html",
                {
                    "request": request,
                    "error": "Cette adresse email a déjà été validée."
                }
            )
        
        # Marquer l'email comme vérifié
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
        print(f"❌ Erreur lors de la validation email: {e}")
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
        # Utiliser Form pour une gestion plus robuste des données
        form_data = await request.form()
        username = form_data.get("username", "").strip()
        password = form_data.get("password", "")
        
        # Validation des données
        if not username or not password:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "errors": ["Veuillez remplir tous les champs."], "username": username},
            )
        
        # Connexion à la base de données
        conn = get_db_connection()
        
        # Vérifier si c'est une connexion MySQL
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
        
        # Vérification de l'utilisateur
        if user is None:
            errors.append("Nom d'utilisateur ou mot de passe incorrect.")
        elif not verify_password(password, user.password_hash):
            errors.append("Nom d'utilisateur ou mot de passe incorrect.")
        elif not user.validated:
            errors.append("Votre inscription n'a pas encore été validée par un administrateur.")
        # Vérification email désactivée pour l'instant
        # elif not user.get("email_verified", True) and not user.get("is_admin", False):
        #     errors.append("Votre adresse email n'a pas encore été validée. Veuillez vérifier votre boîte mail et cliquer sur le lien de confirmation.")
        
        # Si erreurs, afficher le formulaire avec les erreurs
        if errors:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "errors": errors, "username": username},
            )
        
        # Connexion réussie - créer la session sécurisée
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        token = create_secure_session_token(user.id, ip_address, user_agent)
        
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="session_token", 
            value=token, 
            httponly=True, 
            max_age=60 * 60 * 24 * SESSION_MAX_AGE_DAYS,  # Utiliser la constante
            secure=False,  # Mettre True en production avec HTTPS
            samesite="lax"
        )
        return response
        
    except Exception as e:
        # Gestion des erreurs
        print(f"Erreur lors de la connexion: {e}")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "errors": ["Une erreur s'est produite. Veuillez réessayer."], "username": username if 'username' in locals() else ""},
        )


@app.get("/deconnexion")
async def logout(request: Request) -> RedirectResponse:
    """Termine la session de l'utilisateur."""
    token = request.cookies.get("session_token")
    if token:
        # Désactiver la session en base de données
        deactivate_session(token)
    
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_token")
    return response


@app.get("/admin/cleanup-sessions")
async def cleanup_sessions_admin(request: Request) -> dict:
    """Endpoint d'administration pour nettoyer les sessions expirées."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Non autorisé")
    check_admin(user)
    
    try:
        cleanup_expired_sessions()
        return {"status": "success", "message": "Sessions expirées nettoyées avec succès"}
    except Exception as e:
        return {"status": "error", "message": f"Erreur lors du nettoyage : {e}"}


@app.get("/admin/create-sessions-table")
async def create_sessions_table_admin(request: Request) -> dict:
    """Endpoint d'administration pour créer la table user_sessions."""
    # Vérifier l'authentification de manière plus permissive
    user = get_current_user(request)
    if not user:
        # Si pas d'utilisateur, essayer de créer la table quand même (pour le déploiement)
        print("⚠️ Aucun utilisateur connecté, création de la table autorisée")
    else:
        # Vérifier si c'est un admin
        try:
            check_admin(user)
        except:
            print("⚠️ Utilisateur non-admin, création de la table autorisée")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Vérifier si la table existe déjà
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
            return {"status": "info", "message": "Table user_sessions existe déjà"}
        
        # Créer la table
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
            
            # Créer les index
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
            
            # Créer les index
            cur.execute("CREATE INDEX idx_sessions_token ON user_sessions(session_token)")
            cur.execute("CREATE INDEX idx_sessions_user ON user_sessions(user_id)")
            cur.execute("CREATE INDEX idx_sessions_expires ON user_sessions(expires_at)")
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Table user_sessions créée avec succès"}
        
    except Exception as e:
        return {"status": "error", "message": f"Erreur lors de la création de la table : {e}"}


@app.get("/create-sessions-table")
async def create_sessions_table_public() -> dict:
    """Endpoint public pour créer la table user_sessions (pour le déploiement)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Vérifier si la table existe déjà
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
            return {"status": "info", "message": "Table user_sessions existe déjà"}
        
        # Créer la table
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
            
            # Créer les index
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
            
            # Créer les index
            cur.execute("CREATE INDEX idx_sessions_token ON user_sessions(session_token)")
            cur.execute("CREATE INDEX idx_sessions_user ON user_sessions(user_id)")
            cur.execute("CREATE INDEX idx_sessions_expires ON user_sessions(expires_at)")
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Table user_sessions créée avec succès"}
        
    except Exception as e:
        return {"status": "error", "message": f"Erreur lors de la création de la table : {e}"}


def check_admin(user: sqlite3.Row) -> None:
    """Lève une exception si l'utilisateur n'est pas administrateur."""
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Accès réservé à l'administration.")


@app.get("/reservations", response_class=HTMLResponse)
async def reservations_page(request: Request) -> HTMLResponse:
    """Affiche la page de réservation pour les membres validés.

    Montre les réservations existantes pour le jour sélectionné et permet
    d'effectuer une nouvelle réservation si l'horaire est libre.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    if not user.validated:
        return templates.TemplateResponse(
            "not_validated.html",
            {"request": request, "message": "Votre inscription doit être validée pour accéder aux réservations."},
        )
    
    # Paramètres de la requête
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
        
        # Générer toutes les dates de la semaine avec informations formatées
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
    
    # Récupérer les réservations
    conn = get_db_connection()
    
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        from database import get_mysql_cursor_with_names, convert_mysql_result
        execute_with_names = get_mysql_cursor_with_names(conn)
        
        # Réservations pour la date sélectionnée ou la semaine
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
        
        # Réservations de l'utilisateur (toutes)
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
    
    # Générer des créneaux horaires améliorés (6h-23h)
    time_slots: List[Tuple[str, str]] = []
    for hour in range(6, 23):
        start_slot = time(hour, 0)
        end_slot = time(hour + 1, 0) if hour < 22 else time(23, 0)
        time_slots.append((start_slot.strftime("%H:%M"), end_slot.strftime("%H:%M")))
    
    # Préparer la disponibilité avec informations enrichies
    availability: Dict[int, Dict[Tuple[str, str], dict]] = {1: {}, 2: {}, 3: {}}
    reservations_by_court = {1: [], 2: [], 3: []}
    
    for res in reservations:
        reservations_by_court[res.court_number].append(res)
    
    # Pour chaque court et chaque créneau, déterminer la disponibilité
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
    
    # Préparer les données pour la vue semaine (disponibilité par court et par jour)
    week_availability = {}
    month_availability = {}
    
    if view_type == "week" and week_dates:
        for week_date in week_dates:
            date_str = week_date["date"]
            week_availability[date_str] = {}
            
            for court in (1, 2, 3):
                week_availability[date_str][court] = {}
                for start_str, end_str in time_slots:
                    # Chercher les réservations pour ce court, cette date et ce créneau
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
    
    # Préparer les données pour la vue mois
    if view_type == "month":
        # Calculer le début et la fin du mois
        selected_date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
        month_start = selected_date_obj.replace(day=1)
        
        # Formater le titre du mois
        month_names = [
            "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
        ]
        month_title = f"{month_names[selected_date_obj.month - 1]} {selected_date_obj.year}"
        
        # Trouver le dernier jour du mois
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
        
        # Générer toutes les dates du mois
        month_dates = []
        current_date = month_start
        while current_date <= month_end:
            month_dates.append({
                "date": current_date.isoformat(),
                "day_number": current_date.day,
                "is_current_month": True
            })
            current_date += timedelta(days=1)
        
        # Ajouter les jours de la semaine précédente pour compléter la première semaine
        days_before = month_start.weekday()
        for i in range(days_before - 1, -1, -1):
            prev_date = month_start - timedelta(days=i + 1)
            month_dates.insert(0, {
                "date": prev_date.isoformat(),
                "day_number": prev_date.day,
                "is_current_month": False
            })
        
        # Ajouter les jours de la semaine suivante pour compléter la dernière semaine
        days_after = 6 - month_end.weekday()
        for i in range(1, days_after + 1):
            next_date = month_end + timedelta(days=i)
            month_dates.append({
                "date": next_date.isoformat(),
                "day_number": next_date.day,
                "is_current_month": False
            })
        
        # Calculer la disponibilité pour chaque jour du mois
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
    
    # Préparer les données pour le template
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
    """Crée une réservation si l'horaire est disponible.

    Vérifie les conflits avec les réservations existantes sur le même court
    avant d'insérer une nouvelle ligne.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    if not user.validated:
        return templates.TemplateResponse(
            "not_validated.html",
            {"request": request, "message": "Votre inscription doit être validée pour accéder aux réservations."},
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
            errors.append("L'heure de fin doit être postérieure à l'heure de début.")
    except ValueError:
        errors.append("Format de date ou d'heure invalide.")
    if court_number not in (1, 2, 3):
        errors.append("Numéro de court invalide.")
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
    # Vérifier les conflits
    conn = get_db_connection()
    
    # Vérifier si c'est une connexion MySQL
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
                    "Ce créneau n'est pas disponible pour le court choisi. Veuillez sélectionner un autre horaire."
                ],
                "selected_date": date_field,
            },
        )
    # Insertion de la réservation
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
    # Récupérer l'ID de la réservation créée
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
    
    # Récupérer les informations de l'utilisateur pour l'email
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
    """Exporte une réservation vers un fichier ICS pour le calendrier personnel."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Non autorisé")
    
    conn = get_db_connection()
    
    # Récupérer les détails de la réservation
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
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    
    # Vérifier que l'utilisateur est propriétaire de la réservation ou admin
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        reservation_user_id = reservation[1]  # user_id est à l'index 1
        reservation_full_name = reservation[5]  # full_name est à l'index 5
    else:
        reservation_user_id = reservation['user_id']
        reservation_full_name = reservation['full_name']
    
    if reservation_user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    
    # Convertir les données de la réservation
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
        # Gérer le cas où date_str est déjà un objet date (MySQL)
        if isinstance(date_str, date):
            reservation_date = date_str
        else:
            reservation_date = datetime.strptime(str(date_str), "%Y-%m-%d").date()
        
        # Gérer les différents formats de temps (string ou timedelta)
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
        
        # Créer les datetime complets
        start_datetime = datetime.combine(reservation_date, start_time)
        end_datetime = datetime.combine(reservation_date, end_time)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur de format de date: {e}")
    
    # Générer le contenu ICS
    event_title = f"Tennis - Court {court_number}"
    event_description = f"Réservation de tennis sur le court {court_number} avec {reservation_full_name}"
    location = "Club Municipal de Tennis Chihia"
    
    ics_content = generate_ics_content(event_title, event_description, start_datetime, end_datetime, location)
    
    # Créer un fichier temporaire
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


# ===== NOUVELLES ROUTES POUR LES FONCTIONNALITÉS AMÉLIORÉES =====

@app.post("/reservations/recurring", response_class=HTMLResponse)
async def create_recurring_reservation(request: Request) -> HTMLResponse:
    """Crée une réservation récurrente."""
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
    """Annule une réservation."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Non autorisé")
    
    conn = get_db_connection()
    
    # Vérifier que l'utilisateur est propriétaire de la réservation
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM reservations WHERE id = %s", (reservation_id,))
        reservation = cur.fetchone()
    else:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM reservations WHERE id = ?", (reservation_id,))
        reservation = cur.fetchone()
    
    if not reservation:
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    
    reservation_user_id = reservation[0] if hasattr(conn, '_is_mysql') and conn._is_mysql else reservation['user_id']
    
    if reservation_user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    
    # Supprimer la réservation
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur.execute("DELETE FROM reservations WHERE id = %s", (reservation_id,))
    else:
        cur.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    
    conn.commit()
    conn.close()
    
    return JSONResponse({"success": True, "message": "Réservation annulée"})


@app.get("/reservations/calendar")
async def get_calendar_data(request: Request) -> JSONResponse:
    """Retourne les données du calendrier pour l'API."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Non autorisé")
    
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
    
    # Formater les données pour le calendrier
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
        raise HTTPException(status_code=401, detail="Non autorisé")
    
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
    """Ajoute un créneau favori."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Non autorisé")
    
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
    
    return JSONResponse({"success": True, "message": "Créneau favori ajouté"})


@app.get("/reservations/stats")
async def get_user_stats(request: Request) -> JSONResponse:
    """Retourne les statistiques de l'utilisateur."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Non autorisé")
    
    conn = get_db_connection()
    
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        # Statistiques générales
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
        
        # Court préféré
        cur.execute(
            "SELECT court_number, COUNT(*) as count FROM reservations WHERE user_id = %s "
            "GROUP BY court_number ORDER BY count DESC LIMIT 1",
            (user.id,)
        )
        favorite_court = cur.fetchone()
        
    else:
        cur = conn.cursor()
        # Statistiques générales
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
        
        # Court préféré
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
    
    # Récupération des paramètres de pagination
    page = int(request.query_params.get("page", 1))
    per_page = int(request.query_params.get("per_page", 20))
    
    # Calcul des offsets
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Compter le nombre total de membres
    cur.execute("SELECT COUNT(*) FROM users")
    total_members = cur.fetchone()[0]
    
    # Récupérer les membres pour la page courante
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        from database import get_mysql_cursor_with_names, convert_mysql_result
        execute_with_names = get_mysql_cursor_with_names(conn)
        cur, column_names = execute_with_names(
            f"SELECT id, username, full_name, email, phone, ijin_number, birth_date, photo_path, is_admin, validated, is_trainer "
            f"FROM users ORDER BY id LIMIT {per_page} OFFSET {offset}",
            ()
        )
        members = cur.fetchall()
        # Convertir les tuples MySQL en objets avec attributs nommés
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
    
    # Générer les liens de pagination
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
        # Utiliser Form pour une gestion plus robuste des données
        form_data = await request.form()
        
        # Récupération des données du formulaire
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
        
        # Vérifications de base
        errors: List[str] = []
        
        if not username:
            errors.append("Le nom d'utilisateur est obligatoire.")
        if not full_name:
            errors.append("Le nom complet est obligatoire.")
        if not email:
            errors.append("L'adresse e‑mail est obligatoire.")
        if not phone:
            errors.append("Le téléphone est obligatoire.")
        if not birth_date:
            errors.append("La date de naissance est obligatoire.")
        if not password:
            errors.append("Le mot de passe est obligatoire.")
        if password != confirm_password:
            errors.append("Les mots de passe ne correspondent pas.")
        if len(password) < 6:
            errors.append("Le mot de passe doit contenir au moins 6 caractères.")
            
        # Vérifier que le nom d'utilisateur, l'email et le téléphone n'existent pas déjà
        conn = get_db_connection()
        
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            # Vérifier le nom d'utilisateur
            cur.execute("SELECT id, username FROM users WHERE username = %s", (username,))
            existing_user = cur.fetchone()
            if existing_user:
                errors.append("Ce nom d'utilisateur est déjà utilisé.")
            
            # Vérifier l'email
            cur.execute("SELECT id, username, email FROM users WHERE email = %s", (email,))
            existing_email = cur.fetchone()
            if existing_email:
                errors.append(f"Cette adresse email ({email}) est déjà utilisée par l'utilisateur '{existing_email[1]}'. Si c'est votre compte, vous pouvez récupérer votre mot de passe.")
            
            # Vérifier le téléphone
            cur.execute("SELECT id, username, phone FROM users WHERE phone = %s", (phone,))
            existing_phone = cur.fetchone()
            if existing_phone:
                errors.append(f"Ce numéro de téléphone ({phone}) est déjà utilisé par l'utilisateur '{existing_phone[1]}'. Si c'est votre compte, vous pouvez récupérer votre mot de passe.")
        else:
            cur = conn.cursor()
            # Vérifier le nom d'utilisateur
            cur.execute("SELECT id, username FROM users WHERE username = ?", (username,))
            existing_user = cur.fetchone()
            if existing_user:
                errors.append("Ce nom d'utilisateur est déjà utilisé.")
            
            # Vérifier l'email
            cur.execute("SELECT id, username, email FROM users WHERE email = ?", (email,))
            existing_email = cur.fetchone()
            if existing_email:
                errors.append(f"Cette adresse email ({email}) est déjà utilisée par l'utilisateur '{existing_email[1]}'. Si c'est votre compte, vous pouvez récupérer votre mot de passe.")
            
            # Vérifier le téléphone
            cur.execute("SELECT id, username, phone FROM users WHERE phone = ?", (phone,))
            existing_phone = cur.fetchone()
            if existing_phone:
                errors.append(f"Ce numéro de téléphone ({phone}) est déjà utilisé par l'utilisateur '{existing_phone[1]}'. Si c'est votre compte, vous pouvez récupérer votre mot de passe.")
            
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
            
        # Création de l'utilisateur
        pwd_hash = hash_password(password)
        is_trainer = 1 if role == "trainer" else 0
        is_admin = 1 if role == "admin" else 0
        
        # Vérification email désactivée - marquer directement comme vérifié
        email_verification_token = None
        email_verified = 1
        
        # Vérifier si c'est une connexion MySQL
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
        
        print(f"✅ Membre ajouté avec succès par l'admin: {username}")
        
        return RedirectResponse(url="/admin/membres", status_code=303)
        
    except Exception as e:
        print(f"❌ Erreur lors de l'ajout du membre: {e}")
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
    
    # Vérifier si c'est une connexion MySQL
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
    
    # Si le membre vient d'être validé, envoyer un email de confirmation
    if new_state == 1:
        # Récupérer les informations du membre validé
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
    """Permet à un administrateur de supprimer un membre."""
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
        
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            
            # Vérifier que l'utilisateur existe et n'est pas admin
            cur.execute("SELECT username, is_admin FROM users WHERE id = %s", (user_id,))
            member = cur.fetchone()
            
            if not member:
                conn.close()
                return RedirectResponse(url="/admin/membres", status_code=303)
            
            if member[1]:  # MySQL retourne un tuple, is_admin est à l'index 1
                conn.close()
                return RedirectResponse(url="/admin/membres", status_code=303)
            
            # Supprimer l'utilisateur
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        else:
            cur = conn.cursor()
            
            # Vérifier que l'utilisateur existe et n'est pas admin
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
    """Permet à un administrateur de supprimer plusieurs membres en lot."""
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
        
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            
            # Vérifier que les utilisateurs existent et ne sont pas admin
            placeholders = ','.join(['%s' for _ in valid_user_ids])
            cur.execute(f"SELECT id, username, is_admin FROM users WHERE id IN ({placeholders})", valid_user_ids)
            members = cur.fetchall()
            
            # Filtrer les membres non-admin (MySQL retourne des tuples)
            non_admin_members = [m for m in members if not m[2]]  # is_admin est à l'index 2
            non_admin_ids = [m[0] for m in non_admin_members]  # id est à l'index 0
            
            if non_admin_ids:
                # Supprimer les membres non-admin
                placeholders = ','.join(['%s' for _ in non_admin_ids])
                cur.execute(f"DELETE FROM users WHERE id IN ({placeholders})", non_admin_ids)
                conn.commit()
                
                print(f"✅ {len(non_admin_ids)} membres supprimés en lot")
        else:
            cur = conn.cursor()
            
            # Vérifier que les utilisateurs existent et ne sont pas admin
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
                
                print(f"✅ {len(non_admin_ids)} membres supprimés en lot")
        
        conn.close()
        
        return RedirectResponse(url="/admin/membres", status_code=303)
        
    except Exception as e:
        print(f"Erreur lors de la suppression groupée: {e}")
        return RedirectResponse(url="/admin/membres", status_code=303)


@app.get("/admin/membres/{member_id}/details")
async def admin_member_details(request: Request, member_id: int):
    """Retourne les détails d'un membre en JSON pour le modal."""
    user = get_current_user(request)
    if not user:
        return {"status": "error", "message": "Non autorisé"}
    check_admin(user)
    
    try:
        conn = get_db_connection()
        
        # Vérifier si c'est une connexion MySQL
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
            return {"status": "error", "message": "Membre non trouvé"}
        
        # Générer le HTML pour le modal
        html = f"""
        <div class="member-details-content">
            <div class="row">
                <div class="col-md-6">
                    <h6>Informations personnelles</h6>
                    <p><strong>Nom complet:</strong> {member['full_name']}</p>
                    <p><strong>Nom d'utilisateur:</strong> {member['username']}</p>
                    <p><strong>Email:</strong> {member['email'] or 'Non renseigné'}</p>
                    <p><strong>Téléphone:</strong> {member['phone'] or 'Non renseigné'}</p>
                </div>
                <div class="col-md-6">
                    <h6>Informations supplémentaires</h6>
                    <p><strong>Numéro IJIN:</strong> {member['ijin_number'] or 'Non renseigné'}</p>
                    <p><strong>Date de naissance:</strong> {member['birth_date'] or 'Non renseignée'}</p>
                    <p><strong>Rôle:</strong> {'Administrateur' if member['is_admin'] else 'Entraîneur' if member['is_trainer'] else 'Membre'}</p>
                    <p><strong>Statut:</strong> {'Validé' if member['validated'] else 'En attente'}</p>
                </div>
            </div>
        </div>
        """
        
        return {"status": "success", "html": html}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/admin/membres/{member_id}/edit", response_class=HTMLResponse)
async def admin_edit_member_form(request: Request, member_id: int) -> HTMLResponse:
    """Affiche le formulaire d'édition d'un membre."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    try:
        conn = get_db_connection()
        
        # Vérifier si c'est une connexion MySQL
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
            raise HTTPException(status_code=404, detail="Membre non trouvé")
        
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
        print(f"Erreur lors de l'édition: {e}")
        return RedirectResponse(url="/admin/membres", status_code=303)


@app.post("/admin/membres/{member_id}/edit", response_class=HTMLResponse)
async def admin_edit_member(request: Request, member_id: int) -> HTMLResponse:
    """Traite la soumission du formulaire d'édition d'un membre."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    try:
        form_data = await request.form()
        
        # Récupération des données du formulaire
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
        
        # Vérifications de base
        errors: List[str] = []
        
        if not username:
            errors.append("Le nom d'utilisateur est obligatoire.")
        if not full_name:
            errors.append("Le nom complet est obligatoire.")
        
        # Vérifier que le nom d'utilisateur n'existe pas déjà (sauf pour le membre actuel)
        conn = get_db_connection()
        
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = %s AND id != %s", (username, member_id))
        else:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = ? AND id != ?", (username, member_id))
        
        if cur.fetchone():
            errors.append("Ce nom d'utilisateur est déjà utilisé par un autre membre.")
        
        if errors:
            # Récupérer les données du membre pour réafficher le formulaire
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
        
        # Mise à jour du membre
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
                errors.append("Le mot de passe doit contenir au moins 6 caractères.")
            else:
                if hasattr(conn, '_is_mysql') and conn._is_mysql:
                    update_fields.append("password_hash = %s")
                else:
                    update_fields.append("password_hash = ?")
                update_values.append(hash_password(new_password))
        
        if errors:
            # Récupérer les données du membre pour réafficher le formulaire
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
        
        # Ajouter l'ID du membre à la fin pour la clause WHERE
        update_values.append(member_id)
        
        # Exécuter la mise à jour
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        else:
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
        
        cur.execute(query, update_values)
        conn.commit()
        conn.close()
        
        print(f"✅ Membre {username} mis à jour avec succès")
        
        return RedirectResponse(url="/admin/membres", status_code=303)
        
    except Exception as e:
        print(f"❌ Erreur lors de la mise à jour du membre: {e}")
        return RedirectResponse(url="/admin/membres", status_code=303)


@app.get("/admin/reservations", response_class=HTMLResponse)
async def admin_reservations(request: Request) -> HTMLResponse:
    """Affiche toutes les réservations pour les administrateurs avec pagination."""
    try:
        # 1. Vérifier l'utilisateur
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/connexion", status_code=303)
        
        # 2. Vérifier les droits admin
        if not user.is_admin:
                return templates.TemplateResponse(
                    "error.html",
                    {
                        "request": request,
                    "status_code": 403,
                    "detail": "Accès réservé à l'administration. Vous devez être administrateur."
                    },
                status_code=403
                )
            
        # 3. Récupération des paramètres de pagination
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 20))
            
        # Calcul des offsets
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cur = conn.cursor()
                
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            
            # Compter le nombre total de réservations
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM reservations")
            total_bookings = cur.fetchone()[0]
            
            # Récupérer les réservations pour la page courante avec informations utilisateur
            cur, column_names = execute_with_names(f"""
                SELECT r.*, u.username, u.full_name as user_full_name 
                FROM reservations r 
                JOIN users u ON r.user_id = u.id 
                ORDER BY r.date DESC, r.start_time DESC 
                LIMIT {per_page} OFFSET {offset}
            """, ())
            bookings = cur.fetchall()
            # Convertir les tuples MySQL en objets avec attributs nommés
            bookings = [convert_mysql_result(booking, column_names) for booking in bookings]
        else:
            cur = conn.cursor()
            
            # Compter le nombre total de réservations
            cur.execute("SELECT COUNT(*) FROM reservations")
            total_bookings = cur.fetchone()[0]
            
            # Récupérer les réservations pour la page courante avec informations utilisateur
            cur.execute("""
                SELECT r.*, u.username, u.full_name as user_full_name 
                FROM reservations r 
                JOIN users u ON r.user_id = u.id 
                ORDER BY r.date DESC, r.start_time DESC 
                LIMIT ? OFFSET ?
            """, (per_page, offset))
            bookings = cur.fetchall()
        conn.close()
        
        # Convertir les dates en chaînes pour la compatibilité avec le template
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
        
        # Générer les liens de pagination
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
        print(f"❌ Erreur dans admin_reservations: {e}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "status_code": 500,
                "detail": f"Erreur lors du chargement des réservations: {str(e)}"
            },
            status_code=500
        )


@app.post("/admin/reservations/supprimer", response_class=HTMLResponse)
async def admin_delete_reservation(request: Request) -> HTMLResponse:
    """Permet à un administrateur de supprimer une réservation."""
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
    
    # Vérifier si c'est une connexion MySQL
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
    """Permet à un administrateur de supprimer plusieurs réservations en lot."""
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
        
        # Supprimer les réservations
        conn = get_db_connection()
        
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            
            # Utiliser une requête avec IN pour supprimer en lot
            placeholders = ','.join(['%s' for _ in valid_ids])
            cur.execute(f"DELETE FROM reservations WHERE id IN ({placeholders})", valid_ids)
        else:
            cur = conn.cursor()
            
            # Utiliser une requête avec IN pour supprimer en lot
            placeholders = ','.join(['?' for _ in valid_ids])
            cur.execute(f"DELETE FROM reservations WHERE id IN ({placeholders})", valid_ids)
        
        deleted_count = cur.rowcount
        conn.commit()
        conn.close()
        
        print(f"✅ {deleted_count} réservation(s) supprimée(s) en lot")
        
    except Exception as e:
        print(f"❌ Erreur lors de la suppression en lot: {e}")
    
    return RedirectResponse(url="/admin/reservations", status_code=303)


@app.post("/admin/reservations/annuler-lot", response_class=HTMLResponse)
async def admin_cancel_reservations_bulk(request: Request) -> HTMLResponse:
    """Permet à un administrateur d'annuler plusieurs réservations en lot (les supprime)."""
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
        
        # Supprimer les réservations (annulation = suppression)
        conn = get_db_connection()
        
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            cur = conn.cursor()
            
            # Utiliser une requête avec IN pour supprimer en lot
            placeholders = ','.join(['%s' for _ in valid_ids])
            cur.execute(f"DELETE FROM reservations WHERE id IN ({placeholders})", valid_ids)
        else:
            cur = conn.cursor()
            
            # Utiliser une requête avec IN pour supprimer en lot
            placeholders = ','.join(['?' for _ in valid_ids])
            cur.execute(f"DELETE FROM reservations WHERE id IN ({placeholders})", valid_ids)
        
        cancelled_count = cur.rowcount
        conn.commit()
        conn.close()
        
        print(f"✅ {cancelled_count} réservation(s) annulée(s) en lot")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'annulation en lot: {e}")
    
    return RedirectResponse(url="/admin/reservations", status_code=303)


@app.get("/admin/reservations/export")
async def admin_export_reservations(request: Request):
    """Exporte toutes les réservations au format CSV."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Récupérer toutes les réservations avec les informations utilisateur
        cur.execute("""
            SELECT r.id, r.date, r.start_time, r.end_time, r.court_number,
                   u.username, u.full_name, u.email, u.phone
            FROM reservations r 
            JOIN users u ON r.user_id = u.id 
            ORDER BY r.date DESC, r.start_time DESC
        """)
        reservations = cur.fetchall()
        conn.close()
        
        # Créer le contenu CSV
        csv_content = "ID,Date,Début,Fin,Court,Utilisateur,Nom complet,Email,Téléphone\n"
        
        for res in reservations:
            csv_content += f"{res[0]},{res[1]},{res[2]},{res[3]},{res[4]},{res[5]},{res[6]},{res[7] or ''},{res[8] or ''}\n"
        
        # Générer le nom de fichier avec la date
        from datetime import datetime
        filename = f"reservations_cmtch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        print(f"❌ Erreur lors de l'export: {e}")
    return RedirectResponse(url="/admin/reservations", status_code=303)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse:
    """Gestion personnalisée des exceptions HTTP pour les redirections.

    Permet de renvoyer des redirections à partir d'une HTTPException avec le
    code 302 et un champ `detail` indiquant l'URL cible.
    """
    # Si le code est 302, on redirige plutôt que d'afficher l'erreur
    if exc.status_code == 302 and exc.detail:
        return RedirectResponse(url=exc.detail, status_code=exc.status_code)
    # Sinon, on renvoie une page d'erreur générique
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
    """Affiche la liste des articles publiés avec pagination.

    Les articles sont ordonnés par date de création décroissante. Chaque entrée
    présente le titre, une image s'il y en a une et un extrait du contenu.

    Args:
        request: objet Request pour récupérer la session et les URLs.

    Returns:
        Page HTML contenant la liste des articles.
    """
    try:
        # Récupération des paramètres de pagination
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 6))  # 6 articles par page
        
        # Calcul des offsets
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            
            # Compter le nombre total d'articles
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM articles")
            total_articles = cur.fetchone()[0]
        
            # Récupérer les articles pour la page courante
            cur, column_names = execute_with_names("""
                SELECT id, title, content, image_path, created_at, 
                       COALESCE(image_path, '') as image_path_clean
                FROM articles 
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            articles = cur.fetchall()
            # Convertir les tuples MySQL en objets avec attributs nommés
            articles = [convert_mysql_result(article, column_names) for article in articles]
        else:
            cur = conn.cursor()
            
            # Compter le nombre total d'articles
            cur.execute("SELECT COUNT(*) FROM articles")
            total_articles = cur.fetchone()[0]
            
            # Récupérer les articles pour la page courante
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
        
        # Générer les liens de pagination
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
        print(f"❌ Erreur lors de la récupération des articles: {e}")
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
    """Affiche le détail d'un article de presse.

    Args:
        request: objet Request.
        article_id: identifiant de l'article à afficher.

    Returns:
        Page HTML avec le contenu de l'article ou page d'erreur si introuvable.
    """
    try:
        conn = get_db_connection()
        
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            cur, column_names = execute_with_names("SELECT id, title, content, image_path, created_at FROM articles WHERE id = %s", (article_id,))
            article = cur.fetchone()
            # Convertir le tuple MySQL en objet avec attributs nommés
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
        # hébergée derrière un proxy, request.url donnera l'URL complète.
        article_url = str(request.url)
            
        # Récupérer les articles récents pour la sidebar (avant de fermer la connexion)
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            cur, column_names = execute_with_names(
                "SELECT id, title, content, image_path, created_at FROM articles WHERE id != %s ORDER BY created_at DESC LIMIT 5", 
                (article_id,)
            )
            recent_articles = cur.fetchall()
            # Convertir les tuples MySQL en objets avec attributs nommés
            recent_articles = [convert_mysql_result(article, column_names) for article in recent_articles]
        else:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, title, content, image_path, created_at FROM articles WHERE id != ? ORDER BY created_at DESC LIMIT 5", 
                (article_id,)
            )
            recent_articles = cur.fetchall()
        
        # Fermer la connexion après avoir récupéré tous les données
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
        print(f"❌ Erreur dans article_detail: {e}")
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

    Permet aux administrateurs de voir la liste des articles et de créer de
    nouveaux articles. Les administrateurs peuvent supprimer les articles
    existants via cette interface.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    conn = get_db_connection()
    
    # Vérifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        from database import get_mysql_cursor_with_names, convert_mysql_result
        execute_with_names = get_mysql_cursor_with_names(conn)
        cur, column_names = execute_with_names("SELECT id, title, created_at FROM articles ORDER BY created_at DESC")
        articles = cur.fetchall()
        # Convertir les tuples MySQL en objets avec attributs nommés
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
    """Affiche le formulaire de création d'un nouvel article pour les administrateurs."""
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
    """Traite la soumission du formulaire de création d'article.

    Ce gestionnaire prend en charge deux types de formulaires :
    - `multipart/form-data` : permet de télécharger un fichier image depuis le
      navigateur grâce à un champ `<input type="file" name="image_file">`. Le
      fichier est enregistré dans `static/article_images/` avec un nom unique.
    - `application/x-www-form-urlencoded` : permet de spécifier un champ
      `image_url` contenant l'adresse de l'image.

    Dans tous les cas, le titre et le contenu sont requis. Si un champ est
    manquant, une erreur est renvoyée et le formulaire est réaffiché.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    # Déterminer le type de contenu
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
                # Générer un nom unique pour éviter les collisions
                ext = os.path.splitext(filename)[1] or ".bin"
                unique_name = f"{uuid.uuid4().hex}{ext}"
                
                # Upload vers HostGator exclusivement
                try:
                    result = upload_photo_to_imgbb(file_content, unique_name)
                    if result.get('success'):
                        # Utiliser l'URL complète ImgBB pour la base de données
                        image_path = result.get('url')
                        print(f"✅ Image uploadée vers ImgBB: {image_path}")
                    else:
                        # En cas d'échec, utiliser l'image par défaut ImgBB
                        image_path = "https://i.ibb.co/8nBCWmhf/test-image-png.png"
                        print(f"⚠️ Échec upload ImgBB, utilisation image par défaut: {result.get('error')}")
                except Exception as e:
                    # En cas d'erreur, utiliser l'image par défaut ImgBB
                    image_path = "https://i.ibb.co/8nBCWmhf/test-image-png.png"
                    print(f"❌ Erreur HostGator, utilisation image par défaut: {e}")
    else:
        # Analyse du corps form-urlencoded
        form = urllib.parse.parse_qs(body.decode(), keep_blank_values=True)
        title = form.get("title", [""])[0].strip()
        content_text = form.get("content", [""])[0].strip()
        image_path = form.get("image_url", [""])[0].strip()
    
    # Vérifications
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
                # Si le formulaire multipart a été utilisé, l'URL n'est pas disponible
                "image_url": image_path if "multipart/form-data" not in content_type else "",
            },
        )
    
    # Insérer dans la base de données
    conn = get_db_connection()
    
    # Vérifier si c'est une connexion MySQL
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
    
    # Récupérer le chemin de l'image avant de supprimer l'article
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
    
    # Supprimer l'article de la base de données
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
            
            # Vérifier que le fichier existe et le supprimer
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Fichier image supprimé : {file_path}")
        except Exception as e:
            print(f"Erreur lors de la suppression du fichier image : {e}")
    
    return RedirectResponse(url="/admin/articles", status_code=303)


@app.post("/admin/articles/nettoyer-images", response_class=HTMLResponse)
async def admin_cleanup_orphaned_images(request: Request) -> HTMLResponse:
    """Nettoie les images orphelines (images sans article associé)."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    
    conn = get_db_connection()
    
    # Récupérer tous les chemins d'images utilisés dans la base
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
                        print(f"Image orpheline supprimée : {filename}")
                    except Exception as e:
                        print(f"Erreur lors de la suppression de {filename}: {e}")
    
    # Rediriger avec un message de succès
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
    
    # Vérifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        from database import get_mysql_cursor_with_names, convert_mysql_result
        execute_with_names = get_mysql_cursor_with_names(conn)
        cur, column_names = execute_with_names("SELECT id, title, content, image_path, created_at FROM articles WHERE id = %s", (article_id,))
        article = cur.fetchone()
        # Convertir le tuple MySQL en objet avec attributs nommés
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
    
    # Déterminer le type de contenu
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
                # Créer un dossier pour les images si nécessaire
                images_dir = os.path.join(BASE_DIR, "static", "article_images")
                os.makedirs(images_dir, exist_ok=True)
                # Générer un nom unique pour éviter les collisions
                ext = os.path.splitext(filename)[1] or ".bin"
                unique_name = f"{uuid.uuid4().hex}{ext}"
                # Upload vers ImgBB exclusivement
                try:
                    result = upload_photo_to_imgbb(file_content, unique_name)
                    if result.get('success'):
                        image_path = result.get('url')
                        print(f"✅ Image uploadée vers ImgBB: {image_path}")
                    else:
                        # En cas d'échec, utiliser l'image par défaut ImgBB
                        image_path = "https://i.ibb.co/8nBCWmhf/test-image-png.png"
                        print(f"⚠️ Échec upload ImgBB, utilisation image par défaut: {result.get('error')}")
                except Exception as e:
                    # En cas d'erreur, utiliser l'image par défaut ImgBB
                    image_path = "https://i.ibb.co/8nBCWmhf/test-image-png.png"
                    print(f"❌ Erreur HostGator, utilisation image par défaut: {e}")
    else:
        # Formulaire standard urlencoded (image_url fourni par l'utilisateur)
        raw_body = await request.body()
        form = urllib.parse.parse_qs(raw_body.decode(), keep_blank_values=True)
        title = form.get("title", [""])[0].strip()
        content_text = form.get("content", [""])[0].strip()
        image_path = form.get("image_url", [""])[0].strip()
    
    # Vérifications
    if not title:
        errors.append("Le titre est obligatoire.")
    if not content_text:
        errors.append("Le contenu est obligatoire.")
    
    # Si erreurs, récupérer l'article et renvoyer le formulaire avec les champs saisis
    if errors:
        conn = get_db_connection()
        
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            cur, column_names = execute_with_names("SELECT id, title, content, image_path, created_at FROM articles WHERE id = %s", (article_id,))
            article = cur.fetchone()
            # Convertir le tuple MySQL en objet avec attributs nommés
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
        
        # Mettre à jour les valeurs avec celles saisies par l'utilisateur
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
    
    # Mettre à jour dans la base de données
    conn = get_db_connection()
    
    # Vérifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        cur = conn.cursor()
        if image_path:
            # Si une nouvelle image est fournie, mettre à jour l'image aussi
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
            # Si une nouvelle image est fournie, mettre à jour l'image aussi
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
#  Espace utilisateur : statistiques de séances
# -----------------------------------------------------------------------------

@app.get("/test-espace-simple")
async def test_espace_simple(request: Request) -> JSONResponse:
    """Test simple pour diagnostiquer le problème de /espace."""
    try:
        # Test 1: Récupération du cookie
        token = request.cookies.get("session_token")
        if not token:
            return JSONResponse({"error": "Aucun token de session trouvé"})
        
        # Test 2: Parsing du token
        user_id = parse_session_token(token)
        if not user_id:
            return JSONResponse({"error": "Token de session invalide", "token": token})
        
        # Test 3: Récupération de l'utilisateur
        user = get_current_user(request)
        if not user:
            return JSONResponse({"error": "get_current_user retourne None", "user_id": user_id})
        
        # Test 4: Vérification des attributs
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
        
        # Test 5: Vérification du type d'objet
        user_type = type(user).__name__
        user_dir = dir(user)
        
        return JSONResponse({
            "success": True,
            "token": token,
            "user_id": user_id,
            "user_type": user_type,
            "user_attributes": user_attrs,
            "user_dir": user_dir,
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
    """Test de la base de données pour /espace."""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"error": "Utilisateur non connecté"})
        
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
    """Page personnelle affichant les statistiques de réservation par mois.

    Cette page est accessible aux utilisateurs inscrits (membres et entraîneurs)
    et affiche le nombre de séances réservées pour chaque mois. Les données sont
    extraites de la table des réservations en regroupant par année/mois.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    if not user.validated:
        return templates.TemplateResponse(
            "not_validated.html",
            {"request": request, "message": "Votre inscription doit être validée pour accéder à cet espace."},
        )
    conn = get_db_connection()
    
    # Vérifier si c'est une connexion MySQL
    if hasattr(conn, '_is_mysql') and conn._is_mysql:
        from database import get_mysql_cursor_with_names, convert_mysql_result
        execute_with_names = get_mysql_cursor_with_names(conn)
        try:
            # Regrouper par année-mois et compter
            cur, column_names = execute_with_names(
                "SELECT substr(date, 1, 7) AS month, COUNT(*) AS count FROM reservations WHERE user_id = %s GROUP BY month ORDER BY month",
                (user.id,),
            )
            rows = cur.fetchall()
            # Convertir les tuples MySQL en objets avec attributs nommés
            rows = [convert_mysql_result(row, column_names) for row in rows]
        except Exception as e:
            print(f"❌ Erreur dans la requête SQL de /espace: {e}")
            # En cas d'erreur, retourner des données vides
            rows = []
        finally:
            conn.close()
    else:
        cur = conn.cursor()
        try:
            # Regrouper par année-mois et compter
            cur.execute(
                "SELECT substr(date, 1, 7) AS month, COUNT(*) AS count FROM reservations WHERE user_id = ? GROUP BY month ORDER BY month",
                (user.id,),
            )
            rows = cur.fetchall()
        except Exception as e:
            print(f"❌ Erreur dans la requête SQL de /espace: {e}")
            # En cas d'erreur, retourner des données vides
            rows = []
        finally:
            conn.close()
    # Transformer les résultats en listes pour Chart.js
    months: List[str] = []
    counts: List[int] = []
    try:
        for row in rows:
            months.append(row.month)
            counts.append(row.count)
        # Préparer les versions JSON des listes pour Chart.js
        months_js = json.dumps(months)
        counts_js = json.dumps(counts)
        # Préparer les paires pour itération dans le template (mois, count)
        data_pairs = list(zip(months, counts))
        
        # Calculer les statistiques supplémentaires
        total_reservations = sum(counts)
        total_hours = total_reservations  # Chaque réservation = 1 heure
    except Exception as e:
        print(f"❌ Erreur dans la transformation des données de /espace: {e}")
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
#  Endpoint de santé pour Render
# -----------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Point de terminaison de santé pour vérifier l'état de l'application et de la base de données."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Vérifier les tables
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
    """Point de terminaison pour créer des articles de test (débogage uniquement)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Vérifier s'il y a déjà des articles
        cur.execute("SELECT COUNT(*) FROM articles")
        existing_articles = cur.fetchone()[0]
        
        if existing_articles > 0:
            return {
                "status": "info", 
                "message": f"Il y a déjà {existing_articles} article(s) dans la base de données. Utilisez /clear-articles pour les supprimer d'abord."
            }
        
        # Articles de test avec des dates récentes
        test_articles = [
            {
                "title": "Ouverture de la saison 2025",
                "content": "Le Club Municipal de Tennis Chihia est ravi d'annoncer l'ouverture de la saison 2025. Cette année promet d'être exceptionnelle avec de nouveaux équipements et des programmes d'entraînement améliorés pour tous les niveaux.",
                "created_at": (datetime.now() - timedelta(days=2)).isoformat()
            },
            {
                "title": "Nouveau programme pour les jeunes",
                "content": "Nous lançons un nouveau programme spécialement conçu pour les jeunes de 8 à 16 ans. Ce programme combine technique, tactique et plaisir pour développer la passion du tennis chez nos futurs champions.",
                "created_at": (datetime.now() - timedelta(days=5)).isoformat()
            },
            {
                "title": "Tournoi interne du mois",
                "content": "Le tournoi interne du mois de janvier aura lieu le week-end prochain. Tous les membres sont invités à participer. Inscriptions ouvertes jusqu'à vendredi soir.",
                "created_at": (datetime.now() - timedelta(days=8)).isoformat()
            },
            {
                "title": "Maintenance des courts",
                "content": "Nos courts de tennis ont été entièrement rénovés pendant les vacances. Nouvelle surface, filets neufs et éclairage amélioré pour une expérience de jeu optimale.",
                "created_at": (datetime.now() - timedelta(days=12)).isoformat()
            },
            {
                "title": "Bienvenue aux nouveaux membres",
                "content": "Nous souhaitons la bienvenue à tous nos nouveaux membres qui ont rejoint le club ce mois-ci. N'hésitez pas à participer aux activités et à vous intégrer dans notre communauté tennis.",
                "created_at": (datetime.now() - timedelta(days=15)).isoformat()
            }
        ]
        
        # Insérer les articles
        for article in test_articles:
            # Vérifier si c'est une connexion MySQL
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
            "message": f"{len(test_articles)} articles créés",
            "articles": [article["title"] for article in test_articles]
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/init-database")
async def init_database_endpoint():
    """Point de terminaison pour initialiser manuellement la base de données."""
    try:
        from database import init_db
        
        print("🔄 Initialisation manuelle de la base de données...")
        init_db()
        
        return {
            "status": "success",
            "message": "Base de données initialisée avec succès"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de l'initialisation: {str(e)}"
        }

# -----------------------------------------------------------------------------
#  Démarrage de l'application
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.get("/diagnostic-db")
async def diagnostic_db():
    """Point de terminaison de diagnostic pour vérifier l'état de la base de données."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Vérifier si les tables existent
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
        
        # Vérifier l'utilisateur admin
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
    """Point de terminaison de débogage pour vérifier l'état de l'authentification."""
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
                "message": "Utilisateur connecté"
            }
        else:
            return {
                "status": "not_connected",
                "message": "Aucun utilisateur connecté"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur: {str(e)}"
        }


@app.get("/fix-admin")
async def fix_admin_endpoint():
    """Point de terminaison pour créer/corriger l'utilisateur admin UNIQUEMENT si nécessaire."""
    try:
        # D'abord, initialiser la base de données si nécessaire
        from database import init_db
        init_db()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Vérifier si l'utilisateur admin existe
        cur.execute("SELECT * FROM users WHERE username = 'admin'")
        admin_user = cur.fetchone()
        
        if admin_user:
            # Corriger les permissions si nécessaire
            updates = []
            
            if not admin_user[9]:  # is_admin est à l'index 9
                cur.execute("UPDATE users SET is_admin = 1 WHERE username = 'admin'")
                updates.append("droits admin ajoutés")
            
            if not admin_user[10]:  # validated est à l'index 10
                cur.execute("UPDATE users SET validated = 1 WHERE username = 'admin'")
                updates.append("statut validé ajouté")
            
            # Mettre à jour le mot de passe
            admin_password = "admin"
            admin_password_hash = hash_password(admin_password)
            
            if admin_user[2] != admin_password_hash:  # password_hash est à l'index 2
                cur.execute("UPDATE users SET password_hash = %s WHERE username = 'admin'", (admin_password_hash,))
                updates.append("mot de passe mis à jour")
            
            conn.commit()
            
            if updates:
                return {
                    "status": "success",
                    "message": f"Utilisateur admin corrigé: {', '.join(updates)}",
                    "credentials": {
                        "username": "admin",
                        "password": "admin"
                    }
                }
            else:
                return {
                    "status": "success",
                    "message": "Utilisateur admin déjà correct",
                    "credentials": {
                        "username": "admin",
                        "password": "admin"
                    }
                }
        else:
            # Créer l'utilisateur admin
            admin_password = "admin"
            admin_password_hash = hash_password(admin_password)
            
            # Vérifier si c'est une connexion MySQL
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
                "message": "Utilisateur admin créé avec succès",
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
        # Trouver la sauvegarde la plus récente
        latest_backup = find_latest_backup()
        
        if not latest_backup:
            return {
                "status": "error",
                "message": "Aucune sauvegarde trouvée"
            }
        
        # Restaurer la base de données
        if restore_database(latest_backup):
            return {
                "status": "success",
                "message": f"Base de données restaurée depuis {latest_backup}"
            }
        else:
            return {
                "status": "error",
                "message": "Échec de la restauration"
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
        
        # Test de la requête SQL
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        
        # Test de la requête de réservations (pour l'utilisateur 1)
        # Vérifier si c'est une connexion MySQL
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
        
        # Transformer les résultats
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
    """Point de terminaison pour désactiver le système de sauvegarde automatique."""
    try:
        # Créer un fichier de flag pour désactiver la sauvegarde automatique
        flag_file = Path("DISABLE_AUTO_BACKUP")
        flag_file.touch()
        
        return {
            "status": "success",
            "message": "Système de sauvegarde automatique désactivé. Redémarrez l'application pour appliquer."
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la désactivation: {str(e)}"
        }


@app.get("/enable-auto-backup")
async def enable_auto_backup_endpoint():
    """Point de terminaison pour réactiver le système de sauvegarde automatique."""
    try:
        # Supprimer le fichier de flag pour réactiver la sauvegarde automatique
        flag_file = Path("DISABLE_AUTO_BACKUP")
        if flag_file.exists():
            flag_file.unlink()
        
        return {
            "status": "success",
            "message": "Système de sauvegarde automatique réactivé. Redémarrez l'application pour appliquer."
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la réactivation: {str(e)}"
        }







@app.get("/debug-table-structure")
async def debug_table_structure_endpoint():
    """Debug la structure de la table articles"""
    try:
        import sqlite3
        
        # Connexion à la base de données
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # Récupérer la structure de la table articles
        cursor.execute("PRAGMA table_info(articles)")
        columns = cursor.fetchall()
        
        # Récupérer quelques exemples d'articles
        cursor.execute("SELECT * FROM articles LIMIT 3")
        sample_articles = cursor.fetchall()
        
        # Récupérer le total d'articles
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
        
        # Connexion à la base de données
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # Récupérer tous les articles avec leurs détails
        cursor.execute("""
            SELECT id, title, content, image_path, created_at 
            FROM articles 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        articles = cursor.fetchall()
        
        # Récupérer le total d'articles
        cursor.execute("SELECT COUNT(*) FROM articles")
        total_count = cursor.fetchone()[0]
        
        # Tous les articles sont considérés comme publiés (pas de colonne type)
        published_count = total_count
        
        conn.close()
        
        # Analyser chaque article
        analyzed_articles = []
        for article in articles:
            article_id, title, content, image_path, created_at = article
            
            # Vérifier si l'image est accessible
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
    """Diagnostique la base de données"""
    try:
        import sqlite3
        import os
        
        # Vérifier si le fichier de base existe
        db_files = []
        for db_file in ['cmtch.db', 'database.db', 'database.sqlite']:
            if os.path.exists(db_file):
                db_files.append(db_file)
        
        if not db_files:
            return {
                "error": "Aucun fichier de base de données trouvé",
                "searched_files": ['cmtch.db', 'database.db', 'database.sqlite']
            }
        
        # Tester chaque base de données
        results = {}
        for db_file in db_files:
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                
                # Lister toutes les tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                
                # Vérifier si la table articles existe
                has_articles = 'articles' in tables
                
                if has_articles:
                    # Compter les articles
                    cursor.execute("SELECT COUNT(*) FROM articles")
                    article_count = cursor.fetchone()[0]
                    
                    # Récupérer quelques exemples
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
        # Instructions pour obtenir une clé API ImgBB
        instructions = {
            "step1": "Aller sur https://api.imgbb.com/",
            "step2": "Cliquer sur 'Get API Key'",
            "step3": "S'inscrire gratuitement (pas de carte de crédit)",
            "step4": "Copier la clé API",
            "step5": "Remplacer 'YOUR_IMGBB_API_KEY' dans photo_upload_service_imgbb.py",
            "benefits": [
                "Gratuit et illimité",
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
            "next_step": "Obtenir une clé API ImgBB et la configurer"
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/test-db-connection")
async def test_db_connection_endpoint():
    """Test de la connexion à la base de données"""
    try:
        from database import get_db_connection
        import os
        
        # Test de la connexion
        conn = get_db_connection()
        
        # Vérifier le type de connexion
        connection_type = "unknown"
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            connection_type = "mysql"
        elif hasattr(conn, 'execute'):
            connection_type = "sqlite"
        elif hasattr(conn, 'cursor'):
            connection_type = "postgresql"
        
        # Test d'une requête simple
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
            "database_url": os.getenv('DATABASE_URL', 'Non défini'),
            "mysql_available": "mysql.connector" in str(type(conn)),
            "article_count": article_count,
            "connection_object": str(type(conn))
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/test-homepage-data")
async def test_homepage_data_endpoint():
    """Test des données de la page d'accueil"""
    try:
        from database import get_db_connection
        
        # Récupérer les données comme dans la route home
        conn = get_db_connection()
        
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            cur, column_names = execute_with_names(
                "SELECT id, title, content, image_path, created_at FROM articles ORDER BY created_at DESC LIMIT 3"
            )
            latest_articles = cur.fetchall()
            # Convertir les tuples MySQL en objets avec attributs nommés
            latest_articles = [convert_mysql_result(article, column_names) for article in latest_articles]
        else:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, title, content, image_path, created_at FROM articles ORDER BY created_at DESC LIMIT 3"
            )
            latest_articles = cur.fetchall()
        
        conn.close()
        
        # Analyser les données
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
    """Test du système ImgBB"""
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
    """Force la mise à jour de TOUTES les URLs d'images"""
    try:
        import sqlite3
        
        # Connexion à la base de données
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # Récupérer tous les articles
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
            
            # Mettre à jour la base de données
            cursor.execute("UPDATE articles SET image_path = ? WHERE id = ?", (new_url, article_id))
            updated_count += 1
            
            print(f"✅ Article {article_id}: {image_path} -> {new_url}")
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "message": f"{updated_count} articles mis à jour avec les URLs d'images",
            "updated_count": updated_count,
            "new_base_url": "https://www.cmtch.online/image"
        }
        
    except Exception as e:
        return {"error": str(e)}








@app.get("/force-cache-refresh")
async def force_cache_refresh_endpoint():
    """Force le refresh du cache pour résoudre le problème d'images"""
    try:
        # Vider le cache des templates
        templates.env.cache.clear()
        
        # Re-exposer la fonction pour s'assurer qu'elle est bien disponible
        templates.env.globals["ensure_absolute_image_url"] = ensure_absolute_image_url
        
        return {
            "status": "success",
            "message": "Cache vidé et fonction re-exposée",
            "function_available": templates.env.globals.get('ensure_absolute_image_url') is not None
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/test-template-function")
async def test_template_function_endpoint():
    """Test simple pour vérifier que la fonction est accessible dans les templates"""
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
    """Test pour voir le HTML généré avec les URLs d'images"""
    try:
        conn = get_db_connection()
        
        # Récupérer l'article 4
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
            return {"error": "Article 4 non trouvé"}
        
        # Tester la fonction ensure_absolute_image_url
        original_url = article.image_path if hasattr(article, 'image_path') else article[3]
        absolute_url = ensure_absolute_image_url(original_url)
        
        # Vérifier les attributs de l'article
        article_attrs = {}
        if hasattr(article, '__dict__'):
            article_attrs = article.__dict__
        elif hasattr(article, '_fields'):
            # Pour les tuples nommés
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
        
        # Générer le HTML pour voir ce qui est réellement produit
        from fastapi import Request
        from fastapi.templating import Jinja2Templates
        
        # Créer une requête factice pour le template
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
        
        # Extraire la balise img du HTML généré (spécifiquement l'image de l'article)
        import re
        # Chercher l'image avec la classe "article-featured-image"
        img_match = re.search(r'<img[^>]*class="[^"]*article-featured-image[^"]*"[^>]*src="([^"]*)"[^>]*>', rendered_html)
        if not img_match:
            # Si pas trouvé, chercher dans la div "article-image-container"
            img_match = re.search(r'<div[^>]*class="[^"]*article-image-container[^"]*"[^>]*>.*?<img[^>]*src="([^"]*)"[^>]*>', rendered_html, re.DOTALL)
        if not img_match:
            # Si toujours pas trouvé, chercher n'importe quelle image
            img_match = re.search(r'<img[^>]*src="([^"]*)"[^>]*>', rendered_html)
        
        img_src_in_html = img_match.group(1) if img_match else "Non trouvé"
        
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
    """Endpoint pour déboguer les images d'articles"""
    try:
        conn = get_db_connection()
        
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            
            # Récupérer tous les articles
            cur, column_names = execute_with_names("SELECT id, title, image_path FROM articles")
            articles = cur.fetchall()
            # Convertir les tuples MySQL en objets avec attributs nommés
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
        
        # Vérifier si c'est une connexion MySQL
        if hasattr(conn, '_is_mysql') and conn._is_mysql:
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            
            # Récupérer tous les articles
            cur, column_names = execute_with_names("SELECT id, title, image_path FROM articles")
            articles = cur.fetchall()
            # Convertir les tuples MySQL en objets avec attributs nommés
            articles = [convert_mysql_result(article, column_names) for article in articles]
            
            fixed_count = 0
            
            for article in articles:
                article_id = article.id
                title = article.title
                image_path = article.image_path
                
                # Vérifier si l'image est manquante ou invalide
                needs_fix = False
                
                if not image_path or image_path == '':
                    needs_fix = True
                elif not image_path.startswith('https://www.cmtch.online'):
                    needs_fix = True
                elif 'article_images' in image_path and not image_path.endswith('default_article.jpg'):
                    needs_fix = True
                
                if needs_fix:
                    # Utiliser l'image par défaut HostGator
                    default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
                    
                    cur.execute("UPDATE articles SET image_path = %s WHERE id = %s", (default_url, article_id))
                    conn.commit()
                    fixed_count += 1
        else:
            # SQLite
            cur = conn.cursor()
            
            # Récupérer tous les articles
            cur.execute("SELECT id, title, image_path FROM articles")
            articles = cur.fetchall()
            
            fixed_count = 0
            
            for article_id, title, image_path in articles:
                # Vérifier si l'image est manquante ou invalide
                needs_fix = False
                
                if not image_path or image_path == '':
                    needs_fix = True
                elif not image_path.startswith('https://www.cmtch.online'):
                    needs_fix = True
                elif 'article_images' in image_path and not image_path.endswith('default_article.jpg'):
                    needs_fix = True
                
                if needs_fix:
                    # Utiliser l'image par défaut HostGator
                    default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
                    
                    cur.execute("UPDATE articles SET image_path = ? WHERE id = ?", (default_url, article_id))
                    conn.commit()
                    fixed_count += 1
        
        conn.close()
        
        return {
            "status": "success",
            "message": f"Correction terminée: {fixed_count} articles corrigés sur {len(articles)}",
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
    """Point de terminaison pour forcer la désactivation du système de sauvegarde."""
    try:
        # Créer le fichier de flag
        flag_file = Path("DISABLE_AUTO_BACKUP")
        flag_file.touch()
        
        # Vérifier l'état actuel de la base
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
            "message": "Système de sauvegarde FORCÉMENT désactivé",
            "current_data": {
                "users": users_count,
                "articles": articles_count,
                "reservations": reservations_count
            },
            "note": "Vos données actuelles sont préservées. Le système ne touchera plus à votre base."
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la désactivation forcée: {str(e)}"
        }


@app.get("/check-backup-status")
async def check_backup_status_endpoint():
    """Point de terminaison pour vérifier l'état du système de sauvegarde."""
    try:
        flag_file = Path("DISABLE_AUTO_BACKUP")
        is_disabled = flag_file.exists()
        
        # Vérifier l'état de la base
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
                "auto_backup_disabled": True,  # Désactivé par défaut maintenant
                "manual_control": True
            },
            "database": {
                "users": users_count,
                "articles": articles_count,
                "reservations": reservations_count,
                "has_data": users_count > 0 or articles_count > 0 or reservations_count > 0
            },
            "recommendation": "Système désactivé - vos données sont protégées"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la vérification: {str(e)}"
        }



@app.get("/create-admin")
async def create_admin_endpoint():
    """Point de terminaison pour créer l'utilisateur admin si la base est vide."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Vérifier si la base contient des données
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        
        if users_count > 0:
            return {
                "status": "info",
                "message": f"La base contient déjà {users_count} utilisateur(s). Utilisez /fix-admin pour corriger l'admin.",
                "users_count": users_count
            }
        
        # Créer l'utilisateur admin si la base est vide
        admin_password = "admin"
        admin_password_hash = hash_password(admin_password)
        
        # Vérifier si c'est une connexion MySQL
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
            "message": "Base de données vide - Utilisateur admin créé avec succès",
            "credentials": {
                "username": "admin",
                "password": "admin"
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la création: {str(e)}"
        }

@app.get("/backup-database")
async def backup_database_endpoint(request: Request):
    """Endpoint pour créer une sauvegarde de la base de données."""
    try:
        user = get_current_user(request)
        
        if not user or not user.is_admin:
            return {
                "status": "error",
                "message": "Accès refusé - droits administrateur requis"
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
                "message": "Accès refusé - droits administrateur requis"
            }
        
        # Lister les sauvegardes disponibles
        backup_dir = Path("backups")
        if not backup_dir.exists():
            return {
                "status": "success",
                "message": "Aucune sauvegarde trouvée",
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
            "message": f"{len(backup_files)} sauvegarde(s) trouvée(s)",
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
    """Endpoint de test pour diagnostiquer le problème des réservations admin"""
    try:
        user = get_current_user(request)
        
        if not user:
            return {
                "status": "error",
                "message": "Utilisateur non connecté",
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
        
        # Test de connexion à la base de données
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
                "message": f"Erreur de base de données: {str(db_error)}",
                "step": "database_connection",
                "user_info": {
                    "username": user.username,
                    "is_admin": bool(user.is_admin)
                }
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur générale: {str(e)}",
            "step": "general"
        }

@app.get("/test-espace-simple")
async def test_espace_simple(request: Request) -> JSONResponse:
    """Test simple pour diagnostiquer le problème de /espace."""
    try:
        # Test 1: Récupération du cookie
        token = request.cookies.get("session_token")
        if not token:
            return JSONResponse({"error": "Aucun token de session trouvé"})
        
        # Test 2: Parsing du token
        user_id = parse_session_token(token)
        if not user_id:
            return JSONResponse({"error": "Token de session invalide", "token": token})
        
        # Test 3: Récupération de l'utilisateur
        user = get_current_user(request)
        if not user:
            return JSONResponse({"error": "get_current_user retourne None", "user_id": user_id})
        
        # Test 4: Vérification des attributs
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
        
        # Test 5: Vérification du type d'objet
        user_type = type(user).__name__
        user_dir = dir(user)
        
        return JSONResponse({
            "success": True,
            "token": token,
            "user_id": user_id,
            "user_type": user_type,
            "user_attributes": user_attrs,
            "user_dir": user_dir,
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