#!/usr/bin/env python3
"""
Точка входа анализа гипотез.

  .venv/bin/python -m analysis.run_analysis

1) документы Sirena (doc_conflict)
2) «хвост» по маршруту (route_tail)
3) проставление severity из analysis.config
"""

from __future__ import annotations

import json
import sys

from analysis import apply_weights, document_id, shadow_follow
from analysis.config import FINDING_LABELS, HYPOTHESIS_STATUS, SEVERITY
from analysis.db import cursor


def print_summary() -> None:
    print("\n=== Веса (config.SEVERITY) ===")
    for k, v in SEVERITY.items():
        label = FINDING_LABELS.get(k, k)
        print(f"  {k:20} severity={v}  | {label}")

    with cursor() as cur:
        cur.execute(
            """
            SELECT finding_type, count(*), min(severity), max(severity)
            FROM work.finding
            GROUP BY 1
            ORDER BY count(*) DESC
            """
        )
        print("\n=== work.finding ===")
        for t, n, smin, smax in cur.fetchall():
            print(f"  {t:20} n={n:7}  severity={smin}")

        cur.execute(
            "SELECT risk_tier, count(*) FROM work.v_abc GROUP BY 1 ORDER BY 1"
        )
        print("\n=== A/B/C ===")
        for tier, n in cur.fetchall():
            print(f"  {tier}: {n}")

    print("\n=== Статус гипотез (config) ===")
    for key, status in HYPOTHESIS_STATUS.items():
        print(f"  {key:24} {status}")


def main() -> int:
    print("1) Критерий 5 — документы…")
    print(json.dumps(document_id.run(replace=True), ensure_ascii=False, indent=2))

    print("\n2) Хвост route_tail…")
    print(f"  записано: {shadow_follow.run(replace=True)}")

    print("\n3) Применение весов из config…")
    print(json.dumps(apply_weights.apply(), ensure_ascii=False, indent=2))

    print_summary()
    return 0


if __name__ == "__main__":
    sys.exit(main())
