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
créée automatiquement au démarrage avec le nom d'utilisateur « admin » et
le mot de passe « admin ».  Nous invitons les responsables du club à
changer ces identifiants lors du déploiement.

Autor: ChatGPT
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
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

# Clé secrète pour signer les cookies de session.
SECRET_KEY = "change-me-in-production-please"

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
# Expose l'objet datetime dans les templates pour afficher l'année dans le pied de page
templates.env.globals["datetime"] = datetime

# Montage des fichiers statiques (CSS, images, JS)
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)


def create_session_token(user_id: int) -> str:
    """Crée un jeton de session signé pour un utilisateur donné.

    Le jeton est composé de l'identifiant utilisateur codé en ASCII, suivi
    d'un séparateur et d'une signature HMAC basée sur SECRET_KEY. Le tout est
    encodé en base64 URL‑safe afin de pouvoir être stocké dans un cookie.

    Args:
        user_id: identifiant numérique de l'utilisateur.

    Returns:
        Chaîne représentant le jeton de session.
    """
    data = str(user_id).encode()
    signature = hmac.new(SECRET_KEY.encode(), data, hashlib.sha256).hexdigest().encode()
    token_bytes = data + b":" + signature
    return base64.urlsafe_b64encode(token_bytes).decode()


def parse_session_token(token: Optional[str]) -> Optional[int]:
    """Vérifie et décode un jeton de session.

    Args:
        token: Jeton encodé en base64 récupéré depuis le cookie.

    Returns:
        L'identifiant de l'utilisateur si la signature est valide, sinon None.
    """
    if not token:
        return None
    try:
        token_bytes = base64.urlsafe_b64decode(token.encode())
        user_id_bytes, signature = token_bytes.split(b":", 1)
        expected_signature = hmac.new(SECRET_KEY.encode(), user_id_bytes, hashlib.sha256).hexdigest().encode()
        if hmac.compare_digest(signature, expected_signature):
            return int(user_id_bytes.decode())
    except Exception:
        return None
    return None


def hash_password(password: str) -> str:
    """Retourne l'empreinte SHA‑256 d'un mot de passe en clair.

    Args:
        password: Mot de passe en clair.

    Returns:
        Chaîne hexadécimale représentant l'empreinte.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Vérifie qu'un mot de passe correspond à une empreinte enregistrée."""
    return hash_password(password) == password_hash


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


# SYSTÈME DE SAUVEGARDE AUTOMATIQUE POUR RENDER
# Ce système sauvegarde et restaure automatiquement les données
# pour éviter la perte lors des redémarrages de Render

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
                from backup_auto import backup_database
                backup_file = backup_database()
                if backup_file:
                    print(f"✅ Sauvegarde créée: {backup_file}")
                else:
                    print("⚠️ Échec de la sauvegarde")
            else:
                print("📭 Base de données vide - Tentative de restauration")
                # Si la base est vide, essayer de restaurer
                from backup_auto import find_latest_backup, restore_database
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
        # Ne pas bloquer le démarrage de l'application

# IMPORTANT : DÉSACTIVATION COMPLÈTE DU SYSTÈME DE SAUVEGARDE AUTOMATIQUE
# Le système de sauvegarde automatique est DÉSACTIVÉ par défaut
# pour éviter toute interférence avec les données existantes
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
    user_id = parse_session_token(token)
    if not user_id:
        return None
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


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
    telephone = "+216 29 60 03 40"
    email = "club.tennis.chihia@gmail.com"
    description = (
        "Club municipal de tennis Chihia est un lieu spécialement conçu pour les personnes "
        "souhaitant pratiquer le Tennis."
    )
    # Récupérer les trois derniers articles pour les mettre en avant sur l'accueil
    conn = get_db_connection()
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
            "is_admin": bool(user["is_admin"]) if user else False,
            "validated": bool(user["validated"]) if user else False,
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
        if not ijin_number:
            errors.append("Le numéro IJIN est obligatoire.")
        if not birth_date:
            errors.append("La date de naissance est obligatoire.")
        if not password:
            errors.append("Le mot de passe est obligatoire.")
        if password != confirm_password:
            errors.append("Les mots de passe ne correspondent pas.")
        if len(password) < 6:
            errors.append("Le mot de passe doit contenir au moins 6 caractères.")
            
        # Vérifier que le nom d'utilisateur n'existe pas déjà
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            errors.append("Ce nom d'utilisateur est déjà utilisé.")
            
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
        
        cur.execute(
            "INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, photo_path, is_admin, validated, is_trainer) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)",
            (username, pwd_hash, full_name, email, phone, ijin_number, birth_date, "", is_trainer),
        )
        conn.commit()
        conn.close()
        
        print(f"✅ Utilisateur créé avec succès: {username}")
        
        return templates.TemplateResponse(
            "register_success.html",
            {"request": request, "username": username},
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
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()
        
        errors: List[str] = []
        
        # Vérification de l'utilisateur
        if user is None:
            errors.append("Nom d'utilisateur ou mot de passe incorrect.")
        elif not verify_password(password, user["password_hash"]):
            errors.append("Nom d'utilisateur ou mot de passe incorrect.")
        elif not user["validated"]:
            errors.append("Votre inscription n'a pas encore été validée par un administrateur.")
        
        # Si erreurs, afficher le formulaire avec les erreurs
        if errors:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "errors": errors, "username": username},
            )
        
        # Connexion réussie - créer la session
        token = create_session_token(user["id"])
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="session_token", 
            value=token, 
            httponly=True, 
            max_age=60 * 60 * 24 * 7,  # 7 jours
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
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_token")
    return response


def check_admin(user: sqlite3.Row) -> None:
    """Lève une exception si l'utilisateur n'est pas administrateur."""
    if not user or not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Accès réservé à l'administration.")


@app.get("/reservations", response_class=HTMLResponse)
async def reservations_page(request: Request) -> HTMLResponse:
    """Affiche la page de réservation pour les membres validés.

    Montre les réservations existantes pour le jour sélectionné et permet
    d'effectuer une nouvelle réservation si l'horaire est libre.
    """
    user = get_current_user(request)
    if not user:
        # Redirection vers la connexion si l'utilisateur n'est pas connecté
        return RedirectResponse(url="/connexion", status_code=303)
    if not user["validated"]:
        return templates.TemplateResponse(
            "not_validated.html",
            {"request": request, "message": "Votre inscription doit être validée pour accéder aux réservations."},
        )
    # Date sélectionnée (par défaut la date du jour)
    today_str = date.today().isoformat()
    selected_date = request.query_params.get("date", today_str)
    # Récupérer les réservations pour cette date
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT r.*, u.full_name AS user_full_name, u.username FROM reservations r JOIN users u ON r.user_id = u.id "
        "WHERE date = ? ORDER BY start_time",
        (selected_date,),
    )
    reservations = cur.fetchall()
    # Récupérer les réservations de l'utilisateur connecté
    cur.execute(
        "SELECT * FROM reservations WHERE user_id = ? ORDER BY date, start_time",
        (user["id"],),
    )
    user_reservations = cur.fetchall()
    conn.close()
    # Générer des créneaux horaires d'une heure de 8h00 à 22h00 (dernier créneau 21h-22h)
    time_slots: List[Tuple[str, str]] = []
    for hour in range(8, 22):
        start_slot = time(hour, 0)
        end_slot = time(hour + 1, 0) if hour < 21 else time(22, 0)
        time_slots.append((start_slot.strftime("%H:%M"), end_slot.strftime("%H:%M")))
    # Préparer la disponibilité pour chaque court avec informations utilisateur
    availability: Dict[int, Dict[Tuple[str, str], dict]] = {1: {}, 2: {}, 3: {}}
    # Convertir la liste de réservations en dictionnaire par court pour vérifier rapidement
    reservations_by_court = {1: [], 2: [], 3: []}
    for res in reservations:
        reservations_by_court[res["court_number"]].append(res)
    # Pour chaque court et chaque créneau, déterminer si réservé et par qui
    for court in (1, 2, 3):
        court_reservations = reservations_by_court.get(court, [])
        for start_str, end_str in time_slots:
            # On considère le créneau réservé s'il existe une réservation qui chevauche l'intervalle [start, end)
            reserved = False
            reservation_info = None
            for res in court_reservations:
                # res.start_time/res.end_time sont des chaînes HH:MM
                res_start = datetime.strptime(res["start_time"], "%H:%M").time()
                res_end = datetime.strptime(res["end_time"], "%H:%M").time()
                slot_start = datetime.strptime(start_str, "%H:%M").time()
                slot_end = datetime.strptime(end_str, "%H:%M").time()
                # Si les intervalles se chevauchent
                if (slot_start < res_end and slot_end > res_start):
                    reserved = True
                    reservation_info = {
                        "user_full_name": res["user_full_name"],
                        "username": res.get("username", "Utilisateur"),
                        "is_current_user": res["user_id"] == user["id"]
                    }
                    break
            availability[court][(start_str, end_str)] = {
                "reserved": reserved,
                "reservation_info": reservation_info
            }
    return templates.TemplateResponse(
        "reservations.html",
        {
            "request": request,
            "user": user,
            "is_admin": bool(user["is_admin"]),
            "reservations": reservations,
            "user_reservations": user_reservations,
            "selected_date": selected_date,
            "time_slots": time_slots,
            "availability": availability,
        },
    )


@app.post("/reservations", response_class=HTMLResponse)
async def create_reservation(request: Request) -> HTMLResponse:
    """Crée une réservation si l'horaire est disponible.

    Vérifie les conflits avec les réservations existantes sur le même court
    avant d'insérer une nouvelle ligne.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    if not user["validated"]:
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
    cur.execute(
        "INSERT INTO reservations (user_id, court_number, date, start_time, end_time) "
        "VALUES (?, ?, ?, ?, ?)",
        (user["id"], court_number, _date.isoformat(), start_time, end_time),
    )
    conn.commit()
    conn.close()
    redirect_url = f"/reservations?date={_date.isoformat()}"
    return RedirectResponse(url=redirect_url, status_code=303)


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
    cur = conn.cursor()
    cur.execute("SELECT validated FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    new_state = 0 if row["validated"] else 1
    cur.execute("UPDATE users SET validated = ? WHERE id = ?", (new_state, user_id))
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
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ? AND id != ?", (username, member_id))
        if cur.fetchone():
            errors.append("Ce nom d'utilisateur est déjà utilisé par un autre membre.")
        
        if errors:
            # Récupérer les données du membre pour réafficher le formulaire
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
        
        update_fields.append("username = ?")
        update_values.append(username)
        
        update_fields.append("full_name = ?")
        update_values.append(full_name)
        
        update_fields.append("email = ?")
        update_values.append(email)
        
        update_fields.append("phone = ?")
        update_values.append(phone)
        
        update_fields.append("ijin_number = ?")
        update_values.append(ijin_number)
        
        update_fields.append("birth_date = ?")
        update_values.append(birth_date)
        
        update_fields.append("is_admin = ?")
        update_values.append(1 if is_admin else 0)
        
        update_fields.append("validated = ?")
        update_values.append(1 if validated else 0)
        
        update_fields.append("is_trainer = ?")
        update_values.append(1 if is_trainer else 0)
        
        # Si un nouveau mot de passe est fourni
        if new_password:
            if len(new_password) < 6:
                errors.append("Le mot de passe doit contenir au moins 6 caractères.")
            else:
                update_fields.append("password_hash = ?")
                update_values.append(hash_password(new_password))
        
        if errors:
            # Récupérer les données du membre pour réafficher le formulaire
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
        if not user["is_admin"]:
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
        cur = conn.cursor()
        
        # Compter le nombre total d'articles
        cur.execute("SELECT COUNT(*) FROM articles")
        total_articles = cur.fetchone()[0]
        
        # Récupérer les articles pour la page courante
        cur.execute("""
            SELECT id, title, content, image_path, created_at, 
                   COALESCE(image_path, '') as image_path_clean
            FROM articles 
            ORDER BY datetime(created_at) DESC
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
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, content, image_path, created_at FROM articles WHERE id = ?", (article_id,))
    article = cur.fetchone()
    conn.close()
    if article is None:
        raise HTTPException(status_code=404, detail="Article introuvable")
    user = get_current_user(request)
    # Construire une URL absolue pour le partage sur Facebook. Si l'application est
    # hébergée derrière un proxy, request.url donnera l'URL complète.
    article_url = str(request.url)
    return templates.TemplateResponse(
        "article_detail.html",
        {
            "request": request,
            "user": user,
            "article": article,
            "share_url": f"https://www.facebook.com/sharer/sharer.php?u={urllib.parse.quote(article_url, safe='')}",
        },
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

    Ce gestionnaire prend en charge deux types de formulaires :
    - `multipart/form-data` : permet de télécharger un fichier image depuis le
      navigateur grâce à un champ `<input type="file" name="image_file">`. Le
      fichier est enregistré dans `static/article_images/` avec un nom unique.
    - `application/x-www-form-urlencoded` : permet de spécifier un champ
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
                file_path = os.path.join(images_dir, unique_name)
                with open(file_path, "wb") as f:
                    f.write(file_content)
                # Stocker le chemin relatif pour utilisation dans les templates
                image_path = f"/static/article_images/{unique_name}"
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
    # Si erreurs, renvoyer le formulaire avec les champs saisis
    if errors:
        # Indiquer les valeurs précédentes pour pré-remplir le formulaire
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
    cur = conn.cursor()
    cur.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/articles", status_code=303)

# -----------------------------------------------------------------------------
#  Espace utilisateur : statistiques de séances
# -----------------------------------------------------------------------------

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
    if not user["validated"]:
        return templates.TemplateResponse(
            "not_validated.html",
            {"request": request, "message": "Votre inscription doit être validée pour accéder à cet espace."},
        )
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Regrouper par année-mois et compter
        cur.execute(
            "SELECT substr(date, 1, 7) AS month, COUNT(*) AS count FROM reservations WHERE user_id = ? GROUP BY month ORDER BY month",
            (user["id"],),
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
            months.append(row["month"])
            counts.append(row["count"])
        # Préparer les versions JSON des listes pour Chart.js
        months_js = json.dumps(months)
        counts_js = json.dumps(counts)
        # Préparer les paires pour itération dans le template (mois, count)
        data_pairs = list(zip(months, counts))
    except Exception as e:
        print(f"❌ Erreur dans la transformation des données de /espace: {e}")
        # En cas d'erreur, utiliser des listes vides
        months = []
        counts = []
        months_js = json.dumps([])
        counts_js = json.dumps([])
        data_pairs = []
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
                    "id": user["id"],
                    "username": user["username"],
                    "full_name": user["full_name"],
                    "is_admin": bool(user["is_admin"]),
                    "validated": bool(user["validated"]),
                    "is_trainer": bool(user["is_trainer"])
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
            
            if not admin_user['is_admin']:
                cur.execute("UPDATE users SET is_admin = 1 WHERE username = 'admin'")
                updates.append("droits admin ajoutés")
            
            if not admin_user['validated']:
                cur.execute("UPDATE users SET validated = 1 WHERE username = 'admin'")
                updates.append("statut validé ajouté")
            
            # Mettre à jour le mot de passe
            admin_password = "admin"
            admin_password_hash = hash_password(admin_password)
            
            if admin_user['password_hash'] != admin_password_hash:
                cur.execute("UPDATE users SET password_hash = ? WHERE username = 'admin'", (admin_password_hash,))
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
            
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, is_admin, validated, is_trainer)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("admin", admin_password_hash, "Administrateur", "admin@cmtch.tn", "+21612345678", "ADMIN001", "1990-01-01", 1, 1, 0))
            
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
        from backup_auto import find_latest_backup, restore_database
        
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
            months.append(row["month"])
            counts.append(row["count"])
        
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
        
        cur.execute("""
            INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, is_admin, validated, is_trainer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("admin", admin_password_hash, "Administrateur", "admin@cmtch.tn", "+21612345678", "ADMIN001", "1990-01-01", 1, 1, 0))
        
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
        
        if not user or not user["is_admin"]:
            return {
                "status": "error",
                "message": "Accès refusé - droits administrateur requis"
            }
        
        # Importer et exécuter la sauvegarde
        from backup_database import backup_postgresql_db
        result = backup_postgresql_db()
        
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
        
        if not user or not user["is_admin"]:
            return {
                "status": "error",
                "message": "Accès refusé - droits administrateur requis"
            }
        
        # Importer et exécuter la liste des sauvegardes
        from backup_database import list_backups
        result = list_backups()
        
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
        
        if not user["is_admin"]:
            return {
                "status": "error", 
                "message": "Utilisateur non administrateur",
                "step": "admin_check",
                "user_info": {
                    "username": user["username"],
                    "is_admin": bool(user["is_admin"]),
                    "validated": bool(user["validated"])
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
                    "username": user["username"],
                    "is_admin": bool(user["is_admin"]),
                    "validated": bool(user["validated"])
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
                    "username": user["username"],
                    "is_admin": bool(user["is_admin"])
                }
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur générale: {str(e)}",
            "step": "general"
        }