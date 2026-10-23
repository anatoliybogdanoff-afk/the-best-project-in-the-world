"""
meta.norm_loyalty_card — из sql/22_helpers.sql (подсветка IDE).
Маппинг программ должен совпадать с analysis.config.POINTZ_PROGRAM_MAP.
"""

from __future__ import annotations

from pathlib import Path

import asyncpg

from data.analysis.db import execute_script
from data.analysis.person.util import log

HELPERS_SQL = Path(__file__).resolve().parents[2] / "sql" / "22_helpers.sql"


async def ensure_norm_loyalty_card(conn: asyncpg.Connection) -> None:
    """Создаёт/обновляет meta.norm_loyalty_card из sql/22_helpers.sql."""
    log("0c) meta.norm_loyalty_card (sql/22_helpers.sql)…")
    await execute_script(conn, HELPERS_SQL.read_text(encoding="utf-8"))
    log("   функция готова (схема meta — Functions, не Tables)")
