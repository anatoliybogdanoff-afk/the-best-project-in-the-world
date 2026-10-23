"""
Кто такой «человек» в нашей модели.

В источниках нет единого user_id на всех. Склеиваем по картам лояльности:
  • все карты одного forum.forum_cards.profile_id → один человек
  • все карты одного pointz.pointz_cards.user_id → один человек
  • одна и та же карта в разных источниках → тоже один человек
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import asyncpg

from data.analysis.cards import norm_card, norm_card_skyteam
from data.analysis.db import execute_script
from data.analysis.person.util import UnionFind, join_ids, log

ROOT = Path(__file__).resolve().parents[2]
STAGE_DDL = ROOT / "sql" / "21_stage_tables.sql"


async def reset_stage_tables(conn: asyncpg.Connection) -> None:
    """
    Пересоздаёт схему stage и все промежуточные таблицы.

    Это не TEMP: после сборки их видно в DBeaver (stage.flight_event и т.д.).
    """
    log(f"1b) stage DDL: {STAGE_DDL.relative_to(ROOT)}")
    await execute_script(conn, STAGE_DDL.read_text(encoding="utf-8"))


async def build_person_groups(
    conn: asyncpg.Connection,
) -> tuple[dict[str, int], dict[int, dict]]:
    """
    Читает forum/skyteam/pointz и возвращает:
      person_of_card  — карта «FB 123» → person_id (1..N)
      persons         — person_id → карты, имена, profile/user id

    person_id нумеруем стабильно: сортируем группы по минимальной карте.
    """
    log("2) Склеиваю карты → человек (union-find)…")
    uf = UnionFind()
    meta: dict[str, dict] = defaultdict(
        lambda: {
            "forum_profiles": set(),
            "pointz_users": set(),
            "names_forum": set(),
            "names_pointz": set(),
            "names_sirena": set(),
        }
    )

    rows = await conn.fetch(
        """
        SELECT c.programm, c.number, c.profile_id,
               nullif(btrim(coalesce(p.first_name,'') || ' ' || coalesce(p.last_name,'')), '')
        FROM forum.forum_cards c
        LEFT JOIN forum.forum_profiles p ON p.profile_id = c.profile_id
        """
    )
    forum_by_profile: dict[str, list[str]] = defaultdict(list)
    for prog, num, profile_id, fio in rows:
        card = norm_card(prog, num)
        if not card:
            continue
        uf.add(card)
        if profile_id:
            forum_by_profile[profile_id].append(card)
            meta[card]["forum_profiles"].add(profile_id)
        if fio:
            meta[card]["names_forum"].add(fio)
    for cards in forum_by_profile.values():
        for i in range(1, len(cards)):
            uf.union(cards[0], cards[i])

    rows = await conn.fetch(
        """
        SELECT c.bonus_program, c.card_number, c.user_id,
               nullif(btrim(coalesce(u.first_name,'') || ' ' || coalesce(u.last_name,'')), '')
        FROM pointz.pointz_cards c
        LEFT JOIN pointz.pointz_users u ON u.user_id = c.user_id
        """
    )
    pointz_by_user: dict[str, list[str]] = defaultdict(list)
    for prog, num, user_id, fio in rows:
        card = norm_card(prog, num)
        if not card:
            continue
        uf.add(card)
        if user_id:
            pointz_by_user[user_id].append(card)
            meta[card]["pointz_users"].add(user_id)
        if fio:
            meta[card]["names_pointz"].add(fio)
    for cards in pointz_by_user.values():
        for i in range(1, len(cards)):
            uf.union(cards[0], cards[i])

    for row in await conn.fetch(
        "SELECT DISTINCT card_number FROM skyteam.skyteam_flight_cards"
    ):
        card = norm_card_skyteam(row[0])
        if card:
            uf.add(card)

    rows = await conn.fetch(
        """
        SELECT
          upper(substring(paxadditionalinfo from 'FF#([A-Za-z]{2})')),
          substring(paxadditionalinfo from 'FF#[A-Za-z]{2}[[:space:]]*([0-9]+)'),
          nullif(btrim(paxname), '')
        FROM skyteam.sirena_records
        WHERE paxadditionalinfo ~ 'FF#[A-Za-z]{2}'
        """
    )
    for prog, num, fio in rows:
        card = norm_card(prog, num)
        if not card:
            continue
        uf.add(card)
        if fio:
            meta[card]["names_sirena"].add(fio)

    components: dict[str, list[str]] = defaultdict(list)
    for card in uf.parent:
        components[uf.find(card)].append(card)

    person_of_card: dict[str, int] = {}
    persons: dict[int, dict] = {}
    for pid, (_root, cards) in enumerate(
        sorted(components.items(), key=lambda x: min(x[1])), start=1
    ):
        cards_sorted = sorted(set(cards))
        forum_profiles: set[str] = set()
        pointz_users: set[str] = set()
        names_f: set[str] = set()
        names_p: set[str] = set()
        names_s: set[str] = set()
        for c in cards_sorted:
            person_of_card[c] = pid
            m = meta[c]
            forum_profiles |= m["forum_profiles"]
            pointz_users |= m["pointz_users"]
            names_f |= m["names_forum"]
            names_p |= m["names_pointz"]
            names_s |= m["names_sirena"]
        persons[pid] = {
            "cards": cards_sorted,
            "forum_profiles": sorted(forum_profiles),
            "pointz_users": sorted(pointz_users),
            "names_forum": sorted(names_f),
            "names_pointz": sorted(names_p),
            "names_sirena": sorted(names_s),
            "names_distinct_n": len(names_f | names_p | names_s),
        }

    log(f"   карт: {len(person_of_card)}, человек: {len(persons)}")
    return person_of_card, persons


async def insert_person_rows(conn: asyncpg.Connection, persons: dict[int, dict]) -> None:
    """
    Пишет каркас в feat.person_features (цифры) и feat.person_evidence (пояснения).

    person_id задаём явно 1..N — стабильно при том же наборе карт.
    """
    log("3) INSERT в person_features + person_evidence…")
    feat_rows = []
    evid_rows = []
    for pid in sorted(persons):
        p = persons[pid]
        feat_rows.append((pid, len(p["cards"]), p["names_distinct_n"]))
        evid_rows.append(
            (
                pid,
                join_ids(p["cards"]),
                join_ids(p["names_forum"]),
                join_ids(p["names_pointz"]),
                join_ids(p["names_sirena"]),
                join_ids(p["forum_profiles"]),
                join_ids(p["pointz_users"]),
            )
        )

    await conn.executemany(
        """
        INSERT INTO feat.person_features (person_id, cards_n, names_distinct_n)
        VALUES ($1, $2, $3)
        """,
        feat_rows,
    )
    await conn.executemany(
        """
        INSERT INTO feat.person_evidence (
          person_id, card_numbers,
          names_forum, names_pointz, names_sirena,
          forum_profile_ids, pointz_user_ids
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        evid_rows,
    )
    await conn.execute(
        """
        SELECT setval(
          pg_get_serial_sequence('feat.person_features', 'person_id'),
          (SELECT coalesce(max(person_id), 1) FROM feat.person_features)
        )
        """
    )
    log(f"   строк: {len(feat_rows)}")


async def fill_card_person_map(
    conn: asyncpg.Connection, person_of_card: dict[str, int]
) -> None:
    """
    Заполняет stage.card_person (джойны при сборке рейсов).

    Список карт для отчёта — в feat.person.cards (person_entity), не отдельная таблица.
    """
    log("4) stage.card_person…")
    rows = list(person_of_card.items())
    await conn.executemany(
        "INSERT INTO stage.card_person(card_key, person_id) VALUES ($1,$2)",
        rows,
    )
    log(f"   карт в map: {len(person_of_card)}")
