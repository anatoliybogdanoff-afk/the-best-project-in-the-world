"""
Собирает перелёты человека в stage.flight_event / stage.flight_unique.

flight_event — все упоминания с источником и id строки (для evidence)
flight_unique — без дублей источников (для счётчиков и маршрутов)

Нормализация карт — только через meta.norm_loyalty_card (как в Python analysis.cards).
"""

from __future__ import annotations

import asyncpg

from analysis.db import rowcount
from analysis.person.util import log


async def build_person_flights(conn: asyncpg.Connection) -> None:
    """
    Читает skyteam/forum/pointz/sirena → stage.flight_*, обновляет flights_n / даты.

    Дедуп: один рейс в forum+skyteam = две строки в flight_event, одна в flight_unique.
    """
    log("5) Рейсы → stage.flight_event / flight_unique…")

    status = await conn.execute(
        """
        INSERT INTO stage.flight_event
          (person_id, flight_date, flight_number, from_airport, to_airport, src, src_id)
        SELECT cp.person_id,
               NULLIF(btrim(f.date), '')::date,
               btrim(f.flight_number),
               nullif(btrim(f.from_airport), ''),
               nullif(btrim(f.to_airport), ''),
               'skyteam',
               f.skyteam_flight_pk::text
        FROM skyteam.skyteam_flight_cards c
        JOIN skyteam.skyteam_flights f ON f.flight_id = c.flight_id
        JOIN stage.card_person cp
          ON cp.card_key = meta.norm_loyalty_card(NULL, c.card_number)
        WHERE NULLIF(btrim(f.date), '') ~ '^\\d{4}-\\d{2}-\\d{2}$'
          AND NULLIF(btrim(f.flight_number), '') IS NOT NULL
        """
    )
    log(f"   skyteam: {rowcount(status)}")

    status = await conn.execute(
        """
        INSERT INTO stage.flight_event
          (person_id, flight_date, flight_number, from_airport, to_airport, src, src_id)
        SELECT DISTINCT cp.person_id,
               NULLIF(btrim(ff.flight_date), '')::date,
               btrim(ff.flight_number),
               nullif(btrim(ff.dep_airport), ''),
               nullif(btrim(ff.arr_airport), ''),
               'forum',
               ff.forum_flight_id::text
        FROM forum.forum_flights ff
        JOIN forum.forum_cards fc ON fc.profile_id = ff.profile_id
        JOIN stage.card_person cp
          ON cp.card_key = meta.norm_loyalty_card(fc.programm, fc.number)
        WHERE NULLIF(btrim(ff.flight_date), '') ~ '^\\d{4}-\\d{2}-\\d{2}$'
          AND NULLIF(btrim(ff.flight_number), '') IS NOT NULL
        """
    )
    log(f"   forum: {rowcount(status)}")

    status = await conn.execute(
        """
        INSERT INTO stage.flight_event
          (person_id, flight_date, flight_number, from_airport, to_airport, src, src_id)
        SELECT cp.person_id,
               NULLIF(btrim(a.date), '')::date,
               btrim(a.code),
               nullif(btrim(a.departure), ''),
               nullif(btrim(a.arrival), ''),
               'pointz',
               a.pointz_activity_pk::text
        FROM pointz.pointz_activities a
        JOIN pointz.pointz_cards pc ON pc.card_id = a.card_id
        JOIN stage.card_person cp
          ON cp.card_key = meta.norm_loyalty_card(
               pc.bonus_program,
               coalesce(pc.card_number, a.card_number)
             )
        WHERE NULLIF(btrim(a.date), '') ~ '^\\d{4}-\\d{2}-\\d{2}$'
          AND NULLIF(btrim(a.code), '') IS NOT NULL
          AND (
            lower(coalesce(a.activity_type, a.activities_type, '')) LIKE '%flight%'
            OR nullif(btrim(a.departure), '') IS NOT NULL
          )
        """
    )
    log(f"   pointz: {rowcount(status)}")

    status = await conn.execute(
        """
        INSERT INTO stage.flight_event
          (person_id, flight_date, flight_number, from_airport, to_airport, src, src_id)
        SELECT cp.person_id,
               NULLIF(btrim(s.departdate), '')::date,
               btrim(s.flightcode),
               nullif(btrim(s."from"), ''),
               nullif(btrim(s.dest), ''),
               'sirena',
               s.sirena_record_pk::text
        FROM skyteam.sirena_records s
        JOIN stage.card_person cp
          ON cp.card_key = meta.norm_loyalty_card(
               upper(substring(s.paxadditionalinfo from 'FF#([A-Za-z]{2})')),
               substring(s.paxadditionalinfo
                         from 'FF#[A-Za-z]{2}[[:space:]]*([0-9]+)')
             )
        WHERE s.paxadditionalinfo ~ 'FF#[A-Za-z]{2}'
          AND NULLIF(btrim(s.departdate), '') ~ '^\\d{4}-\\d{2}-\\d{2}$'
          AND NULLIF(btrim(s.flightcode), '') IS NOT NULL
        """
    )
    log(f"   sirena: {rowcount(status)}")

    await conn.execute("ANALYZE stage.flight_event")

    status = await conn.execute(
        """
        INSERT INTO stage.flight_unique
          (person_id, flight_date, flight_number, from_airport, to_airport)
        SELECT DISTINCT ON (person_id, flight_date, flight_number, from_airport, to_airport)
               person_id, flight_date, flight_number, from_airport, to_airport
        FROM stage.flight_event
        ORDER BY person_id, flight_date, flight_number, from_airport, to_airport
        """
    )
    log(f"   flight_unique: {rowcount(status)}")
    await conn.execute("ANALYZE stage.flight_unique")

    await conn.execute(
        """
        UPDATE feat.person_features f SET
          flights_n = s.n,
          flight_span_days = GREATEST((s.dmax - s.dmin), 0)
        FROM (
          SELECT person_id, count(*) AS n,
                 min(flight_date) dmin, max(flight_date) dmax
          FROM stage.flight_unique
          GROUP BY person_id
        ) s
        WHERE f.person_id = s.person_id
        """
    )
    await conn.execute(
        """
        UPDATE feat.person_evidence e SET
          first_flight_date = s.dmin,
          last_flight_date = s.dmax
        FROM (
          SELECT person_id, min(flight_date) dmin, max(flight_date) dmax
          FROM stage.flight_unique
          GROUP BY person_id
        ) s
        WHERE e.person_id = s.person_id
        """
    )
    log("   flights_n / даты обновлены")
