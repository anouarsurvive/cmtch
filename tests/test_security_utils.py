# -*- coding: utf-8 -*-
"""Tests security_utils (CSRF, hash, ops)."""
from __future__ import annotations

from security_utils import (
    csrf_tokens_match,
    generate_csrf_token,
    hash_password,
    is_ops_path,
    verify_password,
)


def test_generate_csrf_token_unique():
    a = generate_csrf_token()
    b = generate_csrf_token()
    assert a and b and a != b


def test_csrf_tokens_match():
    t = generate_csrf_token()
    assert csrf_tokens_match(t, t)
    assert not csrf_tokens_match(t, "nope")
    assert not csrf_tokens_match(None, t)


def test_password_hash_roundtrip():
    h = hash_password("secret123")
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_is_ops_path():
    assert is_ops_path("/fix-admin") is True
    assert is_ops_path("/test-espace-simple") is True
    assert is_ops_path("/") is False
    assert is_ops_path("/connexion") is False
