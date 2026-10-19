"""Проставляет severity из analysis.config во все work.finding."""

from __future__ import annotations

from analysis.config import SEVERITY
from analysis.db import cursor


def apply() -> dict[str, int]:
    updated: dict[str, int] = {}
    with cursor() as cur:
        for finding_type, severity in SEVERITY.items():
            cur.execute(
                """
                UPDATE work.finding
                SET severity = %s
                WHERE finding_type = %s
                """,
                (severity, finding_type),
            )
            updated[finding_type] = cur.rowcount
    return updated
