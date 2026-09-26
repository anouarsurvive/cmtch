# -*- coding: utf-8 -*-
"""Dépendances FastAPI : utilisateur courant, login, admin."""
from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import HTTPException, Request

from core.session import get_db_connection, validate_session_token
from db import sql as db_sql


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
            # Connexion SQLite/PostgreSQL — pattern db.sql
            cur = db_sql.execute(conn, "SELECT * FROM users WHERE id = ?", (user_id,))
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



def check_admin(user: sqlite3.Row) -> None:
    """LÃ¨ve une exception si l'utilisateur n'est pas administrateur."""
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="AccÃ¨s rÃ©servÃ© Ã  l'administration.")


