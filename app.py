# -*- coding: utf-8 -*-
"""
Application web pour le Club municipal de tennis Chihia.

Point d'entrée mince (Phase 1) : FastAPI, middleware, static, routers, startup.
Lancer avec : uvicorn app:app
"""
from __future__ import annotations

import os
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from core.config import BASE_DIR
from core.middleware import register_middleware
from core.session import cleanup_expired_sessions, get_db_connection
from core.templates import templates
from db import sql as db_sql
from routers import admin, articles, auth, ops, reservations

# Path pour imports locaux (photo_upload_service_imgbb, etc.)
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

app = FastAPI()
register_middleware(app)

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)

app.include_router(auth.router)
app.include_router(reservations.router)
app.include_router(articles.router)
app.include_router(admin.router)
app.include_router(ops.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse:
    """Gestion personnalisée des exceptions HTTP pour les redirections."""
    if exc.status_code == 302 and exc.detail:
        return RedirectResponse(url=exc.detail, status_code=exc.status_code)
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": exc.status_code, "detail": exc.detail},
        status_code=exc.status_code,
    )


@app.on_event("startup")
async def startup() -> None:
    """Appelé au démarrage de l'application."""
    print("🚀 Démarrage de l'application...")
    print("ℹ️ Initialisation automatique de la base de données désactivée")
    print("ℹ️ Les données existantes sont préservées")

    try:
        conn = get_db_connection()
        users_count = db_sql.fetch_count(conn, "SELECT COUNT(*) FROM users")
        articles_count = db_sql.fetch_count(conn, "SELECT COUNT(*) FROM articles")
        reservations_count = db_sql.fetch_count(conn, "SELECT COUNT(*) FROM reservations")
        print("📊 État de la base de données au démarrage :")
        print(f"   - Utilisateurs : {users_count}")
        print(f"   - Articles : {articles_count}")
        print(f"   - Réservations : {reservations_count}")
        conn.close()
    except Exception as e:
        print(f"⚠️ Impossible de vérifier l'état de la base : {e}")

    try:
        cleanup_expired_sessions()
        print("✅ Nettoyage des sessions expirées effectué")
    except Exception as e:
        print(f"⚠️ Erreur lors du nettoyage des sessions : {e}")

    print("🎉 Application prête !")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )
