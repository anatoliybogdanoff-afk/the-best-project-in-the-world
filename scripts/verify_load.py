#!/usr/bin/env python3
"""Сверка: строки в Postgres == manifest (staging)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "staging" / "manifest.json"

DSN = os.environ.get(
    "DATABASE_URL",
    "host=127.0.0.1 port=5432 dbname=spy_flights user=spy password=spy",
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


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = manifest["tables"]

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    ok = True
    print(f"{'table':28} {'expected':>12} {'db':>12} {'status'}")
    print("-" * 60)
    for table, fname in TABLE_FILE.items():
        exp = expected[fname]
        cur.execute(f"SELECT count(*) FROM {table}")
        got = cur.fetchone()[0]
        status = "OK" if got == exp else "FAIL"
        if status != "OK":
            ok = False
        print(f"{table:28} {exp:12} {got:12} {status}")

    # доп. проверки целостности skyteam
    cur.execute(
        """
        SELECT count(*) FROM skyteam_flight_cards c
        LEFT JOIN skyteam_flights f ON f.flight_id = c.flight_id
        WHERE f.flight_id IS NULL
        """
    )
    orphans = cur.fetchone()[0]
    print(f"\nskyteam orphan cards: {orphans} {'OK' if orphans == 0 else 'FAIL'}")
    if orphans:
        ok = False

    # карточки как текст с пробелом
    cur.execute(
        """
        SELECT card_number FROM skyteam_flight_cards
        WHERE card_number LIKE '% %' LIMIT 1
        """
    )
    sample = cur.fetchone()
    print(f"card_number with space sample: {sample[0]!r}" if sample else "no spaced cards?")

    # boarding: ticket_number не должен стать float-подобным без нулей — просто наличие
    cur.execute("SELECT count(*) FROM boarding_passes WHERE ticket_number IS NOT NULL AND ticket_number <> ''")
    print(f"boarding with ticket_number: {cur.fetchone()[0]}")

    cur.close()
    conn.close()
    print("\nRESULT:", "ALL OK" if ok else "MISMATCH — данные потеряны или не догрузились")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
