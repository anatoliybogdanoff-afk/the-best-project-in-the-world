"""
Нормализация номеров карт лояльности к одному виду: «FB 171388778».

Зачем: в forum номер и программа лежат отдельно, в skyteam уже «FB 123»,
в pointz программа словом («Flying Blue»), в sirena — кусок FF#….
Без единой формы нельзя склеить одного человека из разных таблиц.
"""

from __future__ import annotations

import re

from data.analysis.config import POINTZ_PROGRAM_MAP

_CARD_RE = re.compile(r"^\s*([A-Za-z]{2})\s*[:#]?\s*(\d+)\s*$")
_DIGITS = re.compile(r"\D+")


def norm_card(program: str | None, number: str | None) -> str | None:
    """
    Приводит карту к «XX 123456».

    program — код или название программы (FB / Flying Blue).
    number  — номер (может уже содержать префикс).
    Если разобрать нельзя — None (карту пропускаем).
    """
    if number is None:
        return None
    raw = str(number).strip()
    if not raw:
        return None

    m = _CARD_RE.match(raw)
    if m:
        return f"{m.group(1).upper()} {m.group(2)}"

    prog = (program or "").strip()
    prog = POINTZ_PROGRAM_MAP.get(prog, prog).upper()
    digits = _DIGITS.sub("", raw)
    if len(prog) == 2 and digits:
        return f"{prog} {digits}"
    return None


def norm_card_skyteam(card_number: str | None) -> str | None:
    """То же для skyteam_flight_cards.card_number (обычно уже «FB 123»)."""
    return norm_card(None, card_number)
