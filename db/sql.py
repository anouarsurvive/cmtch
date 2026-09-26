# -*- coding: utf-8 -*-
"""Helpers SQL : adaptation MySQL (? → %s) et exécution."""
from __future__ import annotations

from typing import Any, Optional, Sequence, Tuple


def is_mysql(conn) -> bool:
    """True si la connexion est MySQL (attribut _is_mysql)."""
    return bool(getattr(conn, "_is_mysql", False))


def adapt_sql(conn, sql: str) -> str:
    """Si MySQL : remplace ? par %s (simple replace, OK pour ce codebase)."""
    if is_mysql(conn):
        return sql.replace("?", "%s")
    return sql


def execute(conn, sql: str, params: Optional[Sequence[Any]] = None):
    """Exécute une requête adaptée au backend."""
    cur = conn.cursor()
    cur.execute(adapt_sql(conn, sql), params or ())
    return cur


def fetch_one(conn, sql: str, params: Optional[Sequence[Any]] = None):
    cur = execute(conn, sql, params)
    return cur.fetchone()


def fetch_all(conn, sql: str, params: Optional[Sequence[Any]] = None):
    cur = execute(conn, sql, params)
    return cur.fetchall()


def fetch_count(conn, sql: str, params: Optional[Sequence[Any]] = None) -> int:
    row = fetch_one(conn, sql, params)
    if row is None:
        return 0
    return int(row[0])
