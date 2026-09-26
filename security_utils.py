"""Utilitaires de sécurité : secrets, cookies, CSRF, endpoints ops."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import Optional, Set

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    bcrypt = None  # type: ignore


# Clé secrète : env en priorité, sinon clé éphémère (dev local uniquement)
_env_secret = os.getenv("SECRET_KEY", "").strip()
if _env_secret and _env_secret != "change-me-in-production-please":
    SECRET_KEY = _env_secret
else:
    SECRET_KEY = secrets.token_urlsafe(48)
    print(
        "⚠️ SECRET_KEY absente ou placeholder : clé éphémère utilisée "
        "(les sessions seront invalidées au redémarrage). "
        "Définissez SECRET_KEY en production."
    )

# Cookies sécurisés en HTTPS (prod Render / DATABASE_URL / COOKIE_SECURE=true)
_cookie_secure_env = os.getenv("COOKIE_SECURE", "").strip().lower()
if _cookie_secure_env in ("1", "true", "yes"):
    COOKIE_SECURE = True
elif _cookie_secure_env in ("0", "false", "no"):
    COOKIE_SECURE = False
else:
    # Défaut : sécurisé si on détecte un déploiement cloud
    COOKIE_SECURE = bool(
        os.getenv("RENDER")
        or os.getenv("DATABASE_URL")
        or os.getenv("FORCE_HTTPS")
    )

# Endpoints de diagnostic / ops (désactivés par défaut)
ENABLE_OPS_ENDPOINTS = os.getenv("ENABLE_OPS_ENDPOINTS", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
SETUP_TOKEN = os.getenv("SETUP_TOKEN", "").strip()

OPS_ENDPOINT_PATHS: Set[str] = {
    "/fix-admin",
    "/create-admin",
    "/restore-backup",
    "/init-articles",
    "/init-database",
    "/diagnostic-db",
    "/debug-auth",
    "/test-espace",
    "/test-espace-simple",
    "/test-db-espace",
    "/disable-auto-backup",
    "/enable-auto-backup",
    "/debug-table-structure",
    "/debug-latest-articles",
    "/diagnose-database",
    "/setup-imgbb",
    "/test-db-connection",
    "/test-homepage-data",
    "/test-imgbb",
    "/force-update-all-image-urls",
    "/force-cache-refresh",
    "/test-template-function",
    "/test-html-generation",
    "/debug-article-images",
    "/fix-production-images",
    "/force-disable-backup",
    "/check-backup-status",
    "/test-admin-reservations",
    "/create-sessions-table",
}

# Méthodes HTTP mutantes à protéger CSRF
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Chemins exemptés de CSRF (health, static)
CSRF_EXEMPT_PREFIXES = ("/static/", "/health", "/article_images/")


def hash_password(password: str) -> str:
    """Hash un mot de passe avec bcrypt (fallback SHA-256 si bcrypt absent)."""
    if BCRYPT_AVAILABLE and bcrypt is not None:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    # Fallback dégradé (ne devrait pas arriver en prod si requirements installés)
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def is_bcrypt_hash(password_hash: str) -> bool:
    return bool(password_hash) and (
        password_hash.startswith("$2b$")
        or password_hash.startswith("$2a$")
        or password_hash.startswith("$2y$")
    )


def verify_password(password: str, password_hash: str) -> bool:
    """Vérifie un mot de passe (bcrypt ou SHA-256 legacy)."""
    if not password_hash:
        return False
    if is_bcrypt_hash(password_hash):
        if not BCRYPT_AVAILABLE or bcrypt is None:
            return False
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("utf-8")
            )
        except (ValueError, TypeError):
            return False
    # Legacy SHA-256 (migration progressive)
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy, password_hash)


def needs_rehash(password_hash: str) -> bool:
    """True si le hash est legacy et doit être migré vers bcrypt."""
    return not is_bcrypt_hash(password_hash)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_tokens_match(cookie_token: Optional[str], submitted: Optional[str]) -> bool:
    if not cookie_token or not submitted:
        return False
    return hmac.compare_digest(cookie_token, submitted)


def is_ops_path(path: str) -> bool:
    if path in OPS_ENDPOINT_PATHS:
        return True
    # Doublons éventuels
    if path.rstrip("/") in OPS_ENDPOINT_PATHS:
        return True
    return False


def ops_access_allowed(setup_token: Optional[str] = None) -> bool:
    """
    Accès ops autorisé uniquement si ENABLE_OPS_ENDPOINTS=true
    ET un SETUP_TOKEN valide est fourni (query/header).
    """
    if not ENABLE_OPS_ENDPOINTS:
        return False
    if not SETUP_TOKEN:
        # Ops activés sans token = refusé (force la config)
        return False
    if not setup_token:
        return False
    return hmac.compare_digest(SETUP_TOKEN, setup_token)


def session_cookie_kwargs(max_age: int) -> dict:
    """Arguments communs pour les cookies de session."""
    return {
        "httponly": True,
        "max_age": max_age,
        "secure": COOKIE_SECURE,
        "samesite": "lax",
        "path": "/",
    }
