# -*- coding: utf-8 -*-
"""Tests des helpers db.sql."""
from __future__ import annotations

from db.sql import adapt_sql, is_mysql


class _FakeConn:
    def __init__(self, mysql: bool = False):
        self._is_mysql = mysql


def test_is_mysql_false_by_default():
    assert is_mysql(_FakeConn(False)) is False
    assert is_mysql(object()) is False


def test_is_mysql_true():
    assert is_mysql(_FakeConn(True)) is True


def test_adapt_sql_sqlite_keeps_placeholders():
    sql = "SELECT * FROM users WHERE id = ? AND name = ?"
    assert adapt_sql(_FakeConn(False), sql) == sql


def test_adapt_sql_mysql_replaces_placeholders():
    sql = "SELECT * FROM users WHERE id = ? AND name = ?"
    assert adapt_sql(_FakeConn(True), sql) == (
        "SELECT * FROM users WHERE id = %s AND name = %s"
    )
