#!/usr/bin/env python3
"""Сверка строк в БД с manifest после docker restore."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "dump" / "manifest_row_counts.tsv"


def main() -> int:
    try:
        import psycopg2
    except ImportError:
        print("pip install psycopg2-binary  OR  run via psql manually")
        return 1

    if not MANIFEST.is_file():
        print(f"MISSING {MANIFEST}")
        return 1

    expected: dict[str, int] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        table, cnt = line.split("|", 1)
        expected[table] = int(cnt)

    host = os.getenv("SPY_PG_HOST", "127.0.0.1")
    port = os.getenv("SPY_PG_PORT", "5434")
    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=os.getenv("SPY_PG_DB", "spy_flights"),
        user=os.getenv("SPY_PG_USER", "spy"),
        password=os.getenv("SPY_PG_PASSWORD", "spy"),
    )
    cur = conn.cursor()
    cur.execute(
        """
        SELECT schemaname||'.'||relname, n_live_tup::bigint
        FROM pg_stat_user_tables
        ORDER BY 1
        """
    )
    actual = dict(cur.fetchall())

    cur.execute(
        "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='meta' AND p.proname='norm_loyalty_card'"
    )
    if not cur.fetchone():
        print("FAIL meta.norm_loyalty_card missing")
        return 1

    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    bad: list[str] = []
    for table, exp in sorted(expected.items()):
        act = actual.get(table)
        if act is None:
            bad.append(f"  {table}: expected {exp}, table missing")
        elif act != exp:
            bad.append(f"  {table}: expected {exp}, got {act}")

    if missing:
        print("Tables in manifest but not in DB:", missing)
    if extra:
        print("Extra tables in DB (ok if empty):", extra)

    if bad:
        print("ROW COUNT MISMATCH:")
        print("\n".join(bad))
        return 1

    print(f"OK  {len(expected)} tables match manifest row counts")
    print(f"    feat.person_features = {expected.get('feat.person_features')}")
    print(f"    stage.flight_unique  = {expected.get('stage.flight_unique')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
