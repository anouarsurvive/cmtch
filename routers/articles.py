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

@router.get("/articles", response_class=HTMLResponse)
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


@router.get("/articles/{article_id}", response_class=HTMLResponse)
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


@router.get("/admin/articles", response_class=HTMLResponse)
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


@router.get("/admin/articles/nouveau", response_class=HTMLResponse)
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


@router.post("/admin/articles/nouveau", response_class=HTMLResponse)
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
        
        # URL image saisie manuellement (toujours lue en multipart aussi)
        image_url_field = str(form.get("image_url", "")).strip()

        # Gestion du fichier image s'il existe
        file_field = form.get("image_file")
        if file_field and isinstance(file_field, dict):
            filename = file_field.get("filename")
            file_content = file_field.get("content", b"")
            if filename and file_content:
                # Generer un nom unique pour eviter les collisions
                ext = os.path.splitext(filename)[1] or ".bin"
                unique_name = f"{uuid.uuid4().hex}{ext}"

                # Upload vers ImgBB — pas d'image par defaut silencieuse en cas d'echec
                try:
                    result = upload_photo_to_imgbb(file_content, unique_name)
                    if result.get("success"):
                        image_path = result.get("url") or ""
                        print(f"Image uploadee vers ImgBB: {image_path}")
                    else:
                        detail = result.get("error", "erreur inconnue")
                        errors.append(
                            f"Échec de l'upload de l'image (ImgBB): {detail}. "
                            "Vérifiez IMGBB_API_KEY ou collez une URL d'image."
                        )
                        print(f"Échec upload ImgBB: {detail}")
                except Exception as e:
                    errors.append(
                        f"Échec de l'upload de l'image (ImgBB): {e}. "
                        "Vérifiez IMGBB_API_KEY ou collez une URL d'image."
                    )
                    print(f"Erreur ImgBB: {e}")

        # Si pas d'upload réussi, utiliser l'URL fournie (sinon vide)
        if not image_path and image_url_field:
            image_path = image_url_field
    else:
        # Analyse du corps form-urlencoded
        form = urllib.parse.parse_qs(body.decode(), keep_blank_values=True)
        title = form.get("title", [""])[0].strip()
        content_text = form.get("content", [""])[0].strip()
        image_path = form.get("image_url", [""])[0].strip()
        image_url_field = image_path

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
                "image_url": image_url_field if "multipart/form-data" in content_type else image_path,
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


@router.post("/admin/articles/supprimer", response_class=HTMLResponse)
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


@router.post("/admin/articles/nettoyer-images", response_class=HTMLResponse)
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


@router.get("/admin/articles/modifier/{article_id}", response_class=HTMLResponse)
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


@router.post("/admin/articles/modifier/{article_id}", response_class=HTMLResponse)
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
        image_url_field = str(form.get("image_url", "")).strip()
        # Gestion du fichier image s'il existe
        file_field = form.get("image_file")
        if file_field and isinstance(file_field, dict):
            filename = file_field.get("filename")
            file_content = file_field.get("content", b"")
            if filename and file_content:
                # Generer un nom unique pour eviter les collisions
                ext = os.path.splitext(filename)[1] or ".bin"
                unique_name = f"{uuid.uuid4().hex}{ext}"
                # Upload vers ImgBB — pas d'image par defaut silencieuse en cas d'echec
                try:
                    result = upload_photo_to_imgbb(file_content, unique_name)
                    if result.get("success"):
                        image_path = result.get("url") or ""
                        print(f"Image uploadee vers ImgBB: {image_path}")
                    else:
                        detail = result.get("error", "erreur inconnue")
                        errors.append(
                            f"Échec de l'upload de l'image (ImgBB): {detail}. "
                            "Vérifiez IMGBB_API_KEY ou collez une URL d'image."
                        )
                        print(f"Echec upload ImgBB: {detail}")
                except Exception as e:
                    errors.append(
                        f"Échec de l'upload de l'image (ImgBB): {e}. "
                        "Vérifiez IMGBB_API_KEY ou collez une URL d'image."
                    )
                    print(f"Erreur ImgBB: {e}")

        # Si pas d'upload reussi, utiliser l'URL fournie (sinon garder l'image existante)
        if not image_path and image_url_field:
            image_path = image_url_field
    else:
        # Formulaire standard urlencoded (image_url fourni par l'utilisateur)
        raw_body = await request.body()
        form = urllib.parse.parse_qs(raw_body.decode(), keep_blank_values=True)
        title = form.get("title", [""])[0].strip()
        content_text = form.get("content", [""])[0].strip()
        image_path = form.get("image_url", [""])[0].strip()
    
    # Verifications
    if not title:
        errors.append("Le titre est obligatoire.")
    if not content_text:
        errors.append("Le contenu est obligatoire.")
    
    # Si erreurs, recuperer l'article et renvoyer le formulaire avec les champs saisis
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
