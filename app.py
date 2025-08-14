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
from datetime import datetime, date, time
from typing import Optional, List, Dict, Any, Tuple

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


def get_db_connection() -> sqlite3.Connection:
    """Ouvre une connexion SQLite avec configuration de row_factory.

    Returns:
        Instance de connexion à la base de données.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialise la base de données si nécessaire.

    Crée les tables et un compte administrateur par défaut si elles
    n'existent pas déjà.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    # Table des utilisateurs
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            email TEXT,
            phone TEXT,
            is_admin INTEGER DEFAULT 0,
            validated INTEGER DEFAULT 0
        )
        """
    )
    # Table des réservations
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            court_number INTEGER NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    # Table des articles de presse
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            image_path TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    # Ajouter la colonne is_trainer si elle n'existe pas (prise en charge des entraîneurs)
    # On interroge les métadonnées de la table et on ajoute la colonne si nécessaire.
    try:
        cur.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cur.fetchall()]
        if "is_trainer" not in columns:
            cur.execute("ALTER TABLE users ADD COLUMN is_trainer INTEGER DEFAULT 0")
            conn.commit()
    except Exception:
        # Si l'ajout de colonne échoue (par exemple, en absence de table), on ignore l'erreur
        pass
    # Création du compte admin par défaut si besoin
    cur.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    row = cur.fetchone()
    if row is None:
        admin_pwd = hash_password("admin")
        cur.execute(
            "INSERT INTO users (username, password_hash, full_name, email, phone, is_admin, validated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "admin",
                admin_pwd,
                "Administrateur",
                "admin@example.com",
                "",
                1,
                1,
            ),
        )
        conn.commit()
    conn.close()


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
    """Appelé au démarrage de l'application pour préparer la base de données."""
    init_db()


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
    # Récupérer le corps de la requête et parser les champs manuellement
    raw_body = await request.body()
    form = urllib.parse.parse_qs(raw_body.decode(), keep_blank_values=True)
    username = form.get("username", [""])[0].strip()
    full_name = form.get("full_name", [""])[0].strip()
    email = form.get("email", [""])[0].strip()
    phone = form.get("phone", [""])[0].strip()
    password = form.get("password", [""])[0]
    confirm_password = form.get("confirm_password", [""])[0]
    role = form.get("role", ["member"])[0]
    # Vérifications de base
    errors: List[str] = []
    if not username:
        errors.append("Le nom d'utilisateur est obligatoire.")
    if password != confirm_password:
        errors.append("Les mots de passe ne correspondent pas.")
    conn = get_db_connection()
    cur = conn.cursor()
    # Vérifier que le nom d'utilisateur n'existe pas déjà
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
            },
        )
    # Création de l'utilisateur
    pwd_hash = hash_password(password)
    # Déterminer si l'utilisateur est entraîneur
    is_trainer = 1 if role == "trainer" else 0
    cur.execute(
        "INSERT INTO users (username, password_hash, full_name, email, phone, is_admin, validated, is_trainer) "
        "VALUES (?, ?, ?, ?, ?, 0, 0, ?)",
        (username, pwd_hash, full_name, email, phone, is_trainer),
    )
    conn.commit()
    conn.close()
    return templates.TemplateResponse(
        "register_success.html",
        {"request": request, "username": username},
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
    raw_body = await request.body()
    form = urllib.parse.parse_qs(raw_body.decode(), keep_blank_values=True)
    username = form.get("username", [""])[0].strip()
    password = form.get("password", [""])[0]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cur.fetchone()
    conn.close()
    errors: List[str] = []
    if user is None or not verify_password(password, user["password_hash"]):
        errors.append("Nom d'utilisateur ou mot de passe incorrect.")
    elif not user["validated"]:
        errors.append("Votre inscription n'a pas encore été validée par un administrateur.")
    if errors:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "errors": errors, "username": username},
        )
    token = create_session_token(user["id"])
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="session_token", value=token, httponly=True, max_age=60 * 60 * 24 * 7)
    return response


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
        "SELECT r.*, u.full_name AS user_full_name FROM reservations r JOIN users u ON r.user_id = u.id "
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
    # Préparer la disponibilité pour chaque court
    availability: Dict[int, Dict[Tuple[str, str], bool]] = {1: {}, 2: {}, 3: {}}
    # Convertir la liste de réservations en dictionnaire par court pour vérifier rapidement
    reservations_by_court = {1: [], 2: [], 3: []}
    for res in reservations:
        reservations_by_court[res["court_number"]].append(res)
    # Pour chaque court et chaque créneau, déterminer si réservé
    for court in (1, 2, 3):
        court_reservations = reservations_by_court.get(court, [])
        for start_str, end_str in time_slots:
            # On considère le créneau réservé s'il existe une réservation qui chevauche l'intervalle [start, end)
            reserved = False
            for res in court_reservations:
                # res.start_time/res.end_time sont des chaînes HH:MM
                res_start = datetime.strptime(res["start_time"], "%H:%M").time()
                res_end = datetime.strptime(res["end_time"], "%H:%M").time()
                slot_start = datetime.strptime(start_str, "%H:%M").time()
                slot_end = datetime.strptime(end_str, "%H:%M").time()
                # Si les intervalles se chevauchent
                if (slot_start < res_end and slot_end > res_start):
                    reserved = True
                    break
            availability[court][(start_str, end_str)] = reserved
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
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, full_name, email, phone, is_admin, validated, is_trainer "
        "FROM users ORDER BY id"
    )
    members = cur.fetchall()
    conn.close()
    return templates.TemplateResponse(
        "admin_members.html",
        {
            "request": request,
            "user": user,
            "members": members,
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


@app.get("/admin/reservations", response_class=HTMLResponse)
async def admin_reservations(request: Request) -> HTMLResponse:
    """Affiche toutes les réservations pour les administrateurs."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/connexion", status_code=303)
    check_admin(user)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT r.id, r.court_number, r.date, r.start_time, r.end_time, u.full_name AS user_full_name, u.username "
        "FROM reservations r JOIN users u ON r.user_id = u.id ORDER BY r.date, r.start_time"
    )
    bookings = cur.fetchall()
    conn.close()
    return templates.TemplateResponse(
        "admin_reservations.html",
        {
            "request": request,
            "user": user,
            "bookings": bookings,
        },
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
    """Affiche la liste des articles publiés.

    Les articles sont ordonnés par date de création décroissante. Chaque entrée
    présente le titre, une image s'il y en a une et un extrait du contenu.

    Args:
        request: objet Request pour récupérer la session et les URLs.

    Returns:
        Page HTML contenant la liste des articles.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, content, image_path, created_at FROM articles ORDER BY datetime(created_at) DESC")
    articles = cur.fetchall()
    conn.close()
    user = get_current_user(request)
    return templates.TemplateResponse(
        "articles.html",
        {
            "request": request,
            "user": user,
            "articles": articles,
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