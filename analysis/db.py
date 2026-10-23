"""
Подключение к PostgreSQL через asyncpg.

Переопределение: SPY_PG_HOST / PORT / DB / USER / PASSWORD
или целиком SPY_PG_DSN.
"""

from __future__ import annotations

import os
import re

import asyncpg


def dsn() -> str:
    """DSN для asyncpg.connect."""
    if explicit := os.getenv("SPY_PG_DSN"):
        return explicit
    host = os.getenv("SPY_PG_HOST", "127.0.0.1")
    port = os.getenv("SPY_PG_PORT", "5434")
    db = os.getenv("SPY_PG_DB", "spy_flights")
    user = os.getenv("SPY_PG_USER", "spy")
    password = os.getenv("SPY_PG_PASSWORD", "spy")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def connect() -> asyncpg.Connection:
    """Одно соединение. По умолчанию localhost:5434 / spy_flights / spy."""
    return await asyncpg.connect(dsn())


def rowcount(status: str) -> int:
    """Число затронутых строк из статуса asyncpg (`UPDATE 12`, `INSERT 0 5`)."""
    parts = status.split()
    return int(parts[-1]) if parts else 0


_DOLLAR_TAG = re.compile(r"\$([A-Za-z_]*)\$")


def split_sql_script(sql: str) -> list[str]:
    """
    Режет DDL/SQL-скрипт на отдельные команды по `;` вне строк и dollar-quote.
    asyncpg выполняет только одну команду за execute().
    """
    stmts: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(sql)
    in_single = False
    in_double = False
    dollar_tag: str | None = None

    while i < n:
        ch = sql[i]
        if dollar_tag is not None:
            end = sql.find(dollar_tag, i)
            if end < 0:
                buf.append(sql[i:])
                break
            buf.append(sql[i : end + len(dollar_tag)])
            i = end + len(dollar_tag)
            dollar_tag = None
            continue
        if in_single:
            buf.append(ch)
            if ch == "'" and (i + 1 >= n or sql[i + 1] != "'"):
                in_single = False
            elif ch == "'" and sql[i + 1] == "'":
                buf.append("'")
                i += 2
                continue
            i += 1
            continue
        if in_double:
            buf.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            end = sql.find("\n", i)
            if end < 0:
                break
            buf.append(sql[i : end + 1])
            i = end + 1
            continue
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            end = sql.find("*/", i + 2)
            if end < 0:
                break
            buf.append(sql[i : end + 2])
            i = end + 2
            continue
        if ch == "$":
            m = _DOLLAR_TAG.match(sql, i)
            if m:
                dollar_tag = m.group(0)
                buf.append(dollar_tag)
                i = m.end()
                continue
        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double = True
            buf.append(ch)
            i += 1
            continue
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


async def execute_script(conn: asyncpg.Connection, sql: str) -> None:
    """Выполняет многокомандный SQL-файл (DDL)."""
    for stmt in split_sql_script(sql):
        await conn.execute(stmt)
