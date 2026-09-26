# -*- coding: utf-8 -*-
"""Smoke tests : import FastAPI et présence des routes critiques."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_app_imports_and_has_many_routes():
    from app import app

    assert len(app.routes) >= 70


def test_critical_paths_registered():
    from app import app

    paths = {getattr(r, "path", None) for r in app.routes}
    for path in ("/", "/connexion", "/health", "/reservations", "/articles", "/espace"):
        assert path in paths, f"route manquante: {path}"


def test_test_espace_simple_once_only():
    from app import app

    count = sum(
        1
        for r in app.routes
        if getattr(r, "path", None) == "/test-espace-simple"
    )
    assert count == 1


def test_health_endpoint():
    from app import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
