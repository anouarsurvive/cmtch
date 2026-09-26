# -*- coding: utf-8 -*-
"""Jinja2 templates + CSRF inject + ensure_absolute_image_url."""
from __future__ import annotations

import os
from datetime import datetime

from fastapi.templating import Jinja2Templates

from core.config import BASE_DIR
from core.i18n import detect_language, get_text_align, get_text_direction

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.globals["datetime"] = datetime
templates.env.globals["detect_language"] = detect_language
templates.env.globals["get_text_direction"] = get_text_direction
templates.env.globals["get_text_align"] = get_text_align

_original_template_response = templates.TemplateResponse


def _template_response_with_csrf(name, context, *args, **kwargs):
    """Injecte automatiquement csrf_token dans le contexte Jinja."""
    request = context.get("request") if isinstance(context, dict) else None
    if isinstance(context, dict) and request is not None:
        context.setdefault(
            "csrf_token",
            getattr(request.state, "csrf_token", None)
            or request.cookies.get("csrf_token")
            or "",
        )
    return _original_template_response(name, context, *args, **kwargs)


templates.TemplateResponse = _template_response_with_csrf  # type: ignore[method-assign]


def ensure_absolute_image_url(image_path: str) -> str:
    """S'assure que l'URL de l'image est absolue (ImgBB ou endpoint)."""
    if not image_path:
        return ""

    print(f"🔍 ensure_absolute_image_url: Input = '{image_path}'")

    if image_path.startswith(("http://", "https://")):
        print(f"✅ URL déjà absolue: {image_path}")
        return image_path

    if image_path.startswith("/static/article_images/"):
        filename = image_path.split("/")[-1]
        result = f"https://www.cmtch.online/image/{filename}"
        print(f"🔄 URL relative convertie: {image_path} -> {result}")
        return result

    if not image_path.startswith("/"):
        result = f"https://www.cmtch.online/image/{image_path}"
        print(f"🔄 Nom de fichier converti: {image_path} -> {result}")
        return result

    print(f"⚠️ URL non modifiée: {image_path}")
    return image_path


templates.env.globals["ensure_absolute_image_url"] = ensure_absolute_image_url
print(
    f"🔧 Fonction ensure_absolute_image_url exposée: "
    f"{templates.env.globals.get('ensure_absolute_image_url') is not None}"
)
