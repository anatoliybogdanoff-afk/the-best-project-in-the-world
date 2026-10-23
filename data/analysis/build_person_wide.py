#!/usr/bin/env python3
"""
Сборка витрин по людям.

Схемы:
  forum / skyteam / pointz  — сырые источники
  stage                     — промежуточные таблицы (видны в DBeaver после прогона)
  feat.person_features      — числа для модели
  feat.person_evidence      — пояснения и id строк
  feat.person_card          — карта ↔ person_id

Пороги — analysis/config.py. Драйвер БД — asyncpg.

Запуск:
  .venv/bin/python -m analysis.build_person_wide
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from data.analysis import config
from data.analysis.db import connect, execute_script
from data.analysis.person import person_entity
from data.analysis.person.ensure_ids import ensure_public_row_ids
from data.analysis.person.sources import ensure_source_schemas, relocate_public_tables_if_needed
from data.analysis.person.sql_helpers import ensure_norm_loyalty_card
from data.analysis.person.util import log
from data.analysis.person import cardless, criteria, flights, identity

ROOT = Path(__file__).resolve().parents[1]
DDL_PATH = ROOT / "sql" / "20_person_tables.sql"


async def create_feat_tables(conn) -> None:
    """Пересоздаёт feat.person_features / evidence / person_card по sql/20_person_tables.sql."""
    log(f"1) DDL feat: {DDL_PATH.relative_to(ROOT)}")
    await execute_script(conn, DDL_PATH.read_text(encoding="utf-8"))


async def main() -> int:
    """
    Полный прогон одной транзакцией.

    1) схемы источников + перенос из public (если старая БД)
    2) суррогатные PK строк + meta.norm_loyalty_card
    3) feat + stage таблицы
    4) склейка людей → рейсы → критерии
    """
    t0 = time.time()
    conn = await connect()
    try:
        async with conn.transaction():
            await conn.execute("SET statement_timeout = 0")
            await conn.execute(f"SET work_mem = '{config.BUILD_WORK_MEM}'")

            await ensure_source_schemas(conn)
            await relocate_public_tables_if_needed(conn)
            await ensure_public_row_ids(conn)
            await ensure_norm_loyalty_card(conn)

            await create_feat_tables(conn)
            await identity.reset_stage_tables(conn)

            person_of_card, persons = await identity.build_person_groups(conn)
            await identity.insert_person_rows(conn, persons)
            await identity.fill_card_person_map(conn, person_of_card)

            # без карт: passport / multi-flight Forum↔Sirena → новые person_id + якоря
            await cardless.build_cardless_persons(conn)

            await flights.build_person_flights(conn)

            await criteria.compute_high_freq(conn)
            await criteria.compute_spike(conn)
            await criteria.compute_route_gap_and_quick_return(conn)
            await criteria.compute_flight_conflict(conn)
            await criteria.compute_name_doc_multi(conn)
            await criteria.compute_route_tail(conn)

            await person_entity.build_person_entity(conn)
            await person_entity.build_flight_catalog(conn)

            await criteria.print_summary(conn)

        log(
            f"\nOK за {time.time() - t0:.1f} с\n"
            f"  сырьё:  forum.* / skyteam.* / pointz.*\n"
            f"  stage:  card_person, person_anchor, flight_match, flight_unique, …\n"
            f"  feat:   person_features + person_evidence + person + flight"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
