"""Подключение к PostgreSQL."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg2
import psycopg2.extensions


def connect() -> psycopg2.extensions.connection:
    """Параметры можно переопределить через переменные окружения."""
    return psycopg2.connect(
        host=os.getenv("SPY_PG_HOST", "127.0.0.1"),
        port=int(os.getenv("SPY_PG_PORT", "5434")),
        dbname=os.getenv("SPY_PG_DB", "spy_flights"),
        user=os.getenv("SPY_PG_USER", "spy"),
        password=os.getenv("SPY_PG_PASSWORD", "spy"),
    )


@contextmanager
def cursor() -> Iterator[psycopg2.extensions.cursor]:
    conn = connect()
    try:
        with conn:
            with conn.cursor() as cur:
                yield cur
    finally:
        conn.close()
