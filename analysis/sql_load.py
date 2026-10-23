"""
Загрузка SQL из sql/build/*.sql — файлы подсвечиваются IDE как SQL.

Плейсхолдеры вида __NAME__ подставляются из kwargs.

Почему execute_script, а не один execute:
  asyncpg выполняет только ОДНУ SQL-команду за вызов.
  DDL-файл с несколькими операторами (TRUNCATE; INSERT; …) режется
  по `;` (с учётом строк и $$…$$) и выполняется по частям.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL_BUILD = ROOT / "sql" / "build"

_PLACEHOLDER = re.compile(r"__[A-Z][A-Z0-9_]*__")


def load_sql(name: str, **params: object) -> str:
    """Читает sql/build/{name} и заменяет __KEY__ → str(value)."""
    path = SQL_BUILD / name
    text = path.read_text(encoding="utf-8")
    for key, value in params.items():
        text = text.replace(f"__{key}__", str(value))
    bad = sorted(set(_PLACEHOLDER.findall(text)))
    if bad:
        raise ValueError(f"{path.name}: не подставлены плейсхолдеры {bad}")
    return text
