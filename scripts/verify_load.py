#!/usr/bin/env python3
"""Сверка: строки в Postgres == manifest (staging)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "staging" / "manifest.json"

DSN = os.environ.get(
    "SPY_PG_DSN",
    os.environ.get(
        "DATABASE_URL",
        "postgresql://spy:spy@127.0.0.1:5434/spy_flights",
    ),
)

TABLE_FILE = {
    "forum_profiles": "forum_profiles.csv",
    "forum_documents": "forum_documents.csv",
    "forum_cards": "forum_cards.csv",
    "forum_flights": "forum_flights.csv",
    "skyteam_flights": "skyteam_flights.csv",
    "skyteam_flight_cards": "skyteam_flight_cards.csv",
    "pointz_users": "pointz_users.csv",
    "pointz_cards": "pointz_cards.csv",
    "pointz_activities": "pointz_activities.csv",
    "pointz_errors": "pointz_errors.csv",
    "boarding_passes": "boarding_passes.csv",
}


async def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = manifest["tables"]

    conn = await asyncpg.connect(DSN)
    try:
        ok = True
        print(f"{'table':28} {'expected':>12} {'db':>12} {'status'}")
        print("-" * 60)
        for table, fname in TABLE_FILE.items():
            exp = expected[fname]
            # таблицы могут быть в схемах источников
            got = await conn.fetchval(
                """
                SELECT c.reltuples::bigint
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = $1 AND n.nspname IN ('forum','skyteam','pointz','public')
                ORDER BY CASE n.nspname WHEN 'public' THEN 1 ELSE 0 END
                LIMIT 1
                """,
                table,
            )
            # точный count
            schema = await conn.fetchval(
                """
                SELECT n.nspname FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = $1 AND n.nspname IN ('forum','skyteam','pointz','public')
                ORDER BY CASE n.nspname WHEN 'public' THEN 1 ELSE 0 END
                LIMIT 1
                """,
                table,
            )
            if schema is None:
                print(f"{table:28} {exp:12} {'MISSING':>12} FAIL")
                ok = False
                continue
            got = await conn.fetchval(f"SELECT count(*) FROM {schema}.{table}")
            status = "OK" if got == exp else "FAIL"
            if status != "OK":
                ok = False
            print(f"{table:28} {exp:12} {got:12} {status}")

        orphans = await conn.fetchval(
            """
            SELECT count(*) FROM skyteam.skyteam_flight_cards c
            LEFT JOIN skyteam.skyteam_flights f ON f.flight_id = c.flight_id
            WHERE f.flight_id IS NULL
            """
        )
        print(f"\nskyteam orphan cards: {orphans} {'OK' if orphans == 0 else 'FAIL'}")
        if orphans:
            ok = False

        sample = await conn.fetchval(
            """
            SELECT card_number FROM skyteam.skyteam_flight_cards
            WHERE card_number LIKE '% %' LIMIT 1
            """
        )
        print(f"card_number with space sample: {sample!r}" if sample else "no spaced cards?")

        n_ticket = await conn.fetchval(
            """
            SELECT count(*) FROM skyteam.boarding_passes
            WHERE ticket_number IS NOT NULL AND ticket_number <> ''
            """
        )
        print(f"boarding with ticket_number: {n_ticket}")
        return 0 if ok else 1
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
