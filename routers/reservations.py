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

@router.get("/reservations", response_class=HTMLResponse)
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


@router.post("/reservations", response_class=HTMLResponse)
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


@router.get("/reservations/{reservation_id}/export-ics")
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

@router.post("/reservations/recurring", response_class=HTMLResponse)
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


@router.delete("/reservations/{reservation_id}")
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


@router.get("/reservations/calendar")
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


@router.get("/reservations/notifications")
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


@router.post("/reservations/favorites")
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


@router.get("/reservations/stats")
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

