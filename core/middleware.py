# -*- coding: utf-8 -*-
"""Enregistrement des middlewares securite + session."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from security_utils import (
    COOKIE_SECURE,
    CSRF_EXEMPT_PREFIXES,
    UNSAFE_METHODS,
    csrf_tokens_match,
    generate_csrf_token,
    is_ops_path,
    ops_access_allowed,
    session_cookie_kwargs,
)
from core.config import SESSION_MAX_AGE_DAYS
from core.session import (
    create_secure_session_token,
    deactivate_session,
    should_refresh_token,
    validate_session_token,
)


def register_middleware(app: FastAPI) -> None:
    """Attache les middlewares HTTP securite (CSRF/ops) et session."""

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
