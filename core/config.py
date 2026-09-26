# -*- coding: utf-8 -*-
"""Configuration centrale et chemins."""
from __future__ import annotations

import os

from security_utils import session_cookie_kwargs  # re-export pour convenience

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database.db")

SESSION_TIMEOUT_MINUTES = 30
SESSION_MAX_AGE_DAYS = 7
SESSION_REFRESH_THRESHOLD = 15

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@cmtch.tn")

__all__ = [
    "BASE_DIR",
    "DB_PATH",
    "SESSION_TIMEOUT_MINUTES",
    "SESSION_MAX_AGE_DAYS",
    "SESSION_REFRESH_THRESHOLD",
    "SMTP_SERVER",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "EMAIL_FROM",
    "session_cookie_kwargs",
]
