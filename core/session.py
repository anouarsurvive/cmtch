# -*- coding: utf-8 -*-
"""Tokens et gestion des sessions sécurisées."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional

from security_utils import SECRET_KEY
from core.config import (
    SESSION_MAX_AGE_DAYS,
    SESSION_REFRESH_THRESHOLD,
    SESSION_TIMEOUT_MINUTES,
)


def get_db_connection():
    from database import get_db_connection as get_db_conn
    return get_db_conn()


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
    

