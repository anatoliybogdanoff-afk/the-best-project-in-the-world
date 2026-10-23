"""Мелкие общие штуки для сборки витрин."""

from __future__ import annotations


def log(msg: str) -> None:
    """Печать прогресса сразу в консоль (без буфера)."""
    print(msg, flush=True)


def join_ids(values: set[str] | list[str]) -> str | None:
    """
    Склеивает набор строк через « | » для колонок-пояснений.

    Без лимита: обрезка evidence недопустима (теряются id для проверки).
    """
    vals = sorted({v for v in values if v})
    if not vals:
        return None
    return " | ".join(vals)


class UnionFind:
    """
    Склейка карт в «одного человека».

    Каждая карта — узел. Если две карты принадлежат одному forum-профилю
    или одному pointz-user, делаем union. В конце компонента = один person_id.
    """

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        """Регистрирует карту, если её ещё не было."""
        if x not in self.parent:
            self.parent[x] = x

    def find(self, x: str) -> str:
        """Корень компоненты (сжатие пути)."""
        self.add(x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        """Объединяет две карты в одну группу «это один человек»."""
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra
