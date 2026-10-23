"""
Собирает перелёты человека в stage.flight_event / stage.flight_unique.

flight_event — все упоминания с источником и id строки (для evidence)
flight_unique — без дублей источников (для счётчиков и маршрутов)

Номер рейса / аэропорты нормализуем в UPPER, чтобы forum+skyteam+sirena
с одним коммерческим рейсом не плодили два «уникальных» из‑за регистра.

Страны: forum даёт dep/arr_country; для остальных — stage.airport_country
(мода страны по IATA из forum).
"""

from __future__ import annotations

import asyncpg

from analysis.db import rowcount
from analysis.person.util import log


async def build_person_flights(conn: asyncpg.Connection) -> None:
    """
    Читает skyteam/forum/pointz/sirena → stage.flight_*, обновляет flights_n / даты.

    Дедуп: один рейс в forum+skyteam = две строки в flight_event, одна в flight_unique
    при совпадении дата+номер+OD (после upper).
    """
    log("5) Рейсы → stage.flight_event / flight_unique…")
    await _fill_airport_country(conn)

    status = await conn.execute(
        """
        INSERT INTO stage.flight_event
          (person_id, flight_date, flight_number, from_airport, to_airport, src, src_id)
        SELECT cp.person_id,
               NULLIF(btrim(f.date), '')::date,
               upper(btrim(f.flight_number)),
               upper(coalesce(nullif(btrim(f.from_airport), ''), '')),
               upper(coalesce(nullif(btrim(f.to_airport), ''), '')),
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
               upper(btrim(ff.flight_number)),
               upper(coalesce(nullif(btrim(ff.dep_airport), ''), '')),
               upper(coalesce(nullif(btrim(ff.arr_airport), ''), '')),
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
               upper(btrim(a.code)),
               upper(coalesce(nullif(btrim(a.departure), ''), '')),
               upper(coalesce(nullif(btrim(a.arrival), ''), '')),
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
               upper(btrim(s.flightcode)),
               upper(coalesce(nullif(btrim(s."from"), ''), '')),
               upper(coalesce(nullif(btrim(s.dest), ''), '')),
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
    log(f"   sirena (по FF#): {rowcount(status)}")

    status = await conn.execute(
        """
        INSERT INTO stage.flight_event
          (person_id, flight_date, flight_number, from_airport, to_airport, src, src_id)
        SELECT DISTINCT pa.person_id,
               NULLIF(btrim(ff.flight_date), '')::date,
               upper(btrim(ff.flight_number)),
               upper(coalesce(nullif(btrim(ff.dep_airport), ''), '')),
               upper(coalesce(nullif(btrim(ff.arr_airport), ''), '')),
               'forum',
               ff.forum_flight_id::text
        FROM forum.forum_flights ff
        JOIN stage.person_anchor pa
          ON pa.anchor_type = 'forum_profile'
         AND pa.anchor_key = ff.profile_id
        WHERE NULLIF(btrim(ff.flight_date), '') ~ '^\\d{4}-\\d{2}-\\d{2}$'
          AND NULLIF(btrim(ff.flight_number), '') IS NOT NULL
        """
    )
    log(f"   forum (по anchor): {rowcount(status)}")

    status = await conn.execute(
        """
        INSERT INTO stage.flight_event
          (person_id, flight_date, flight_number, from_airport, to_airport, src, src_id)
        SELECT pa.person_id,
               NULLIF(btrim(s.departdate), '')::date,
               upper(btrim(s.flightcode)),
               upper(coalesce(nullif(btrim(s."from"), ''), '')),
               upper(coalesce(nullif(btrim(s.dest), ''), '')),
               'sirena',
               s.sirena_record_pk::text
        FROM skyteam.sirena_records s
        JOIN stage.person_anchor pa
          ON pa.anchor_type = 'sirena_doc'
         AND pa.anchor_key = upper(
               regexp_replace(btrim(s.traveldoc), '[^0-9A-Za-z]', '', 'g')
             )
        WHERE coalesce(btrim(s.traveldoc), '') NOT IN ('', 'N/A')
          AND NOT (coalesce(s.paxadditionalinfo, '') ~ 'FF#[A-Za-z]{2}')
          AND NULLIF(btrim(s.departdate), '') ~ '^\\d{4}-\\d{2}-\\d{2}$'
          AND NULLIF(btrim(s.flightcode), '') IS NOT NULL
        """
    )
    log(f"   sirena (по doc): {rowcount(status)}")

    await conn.execute("ANALYZE stage.flight_event")

    # дедуп + страны через справочник IATA→country (из forum)
    status = await conn.execute(
        """
        INSERT INTO stage.flight_unique (
          person_id, flight_date, flight_number,
          from_airport, to_airport, from_country, to_country
        )
        SELECT
          e.person_id,
          e.flight_date,
          e.flight_number,
          e.from_airport,
          e.to_airport,
          ac_from.country,
          ac_to.country
        FROM (
          SELECT DISTINCT
            person_id, flight_date, flight_number, from_airport, to_airport
          FROM stage.flight_event
        ) e
        LEFT JOIN stage.airport_country ac_from ON ac_from.airport = e.from_airport
        LEFT JOIN stage.airport_country ac_to   ON ac_to.airport = e.to_airport
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


async def _fill_airport_country(conn: asyncpg.Connection) -> None:
    """Мода страны по аэропорту из forum (единственный источник со страной)."""
    status = await conn.execute(
        """
        INSERT INTO stage.airport_country (airport, country)
        SELECT airport, country
        FROM (
          SELECT
            upper(btrim(airport)) AS airport,
            btrim(country) AS country,
            row_number() OVER (
              PARTITION BY upper(btrim(airport))
              ORDER BY count(*) DESC, btrim(country)
            ) AS rn
          FROM (
            SELECT dep_airport AS airport, dep_country AS country
            FROM forum.forum_flights
            UNION ALL
            SELECT arr_airport, arr_country
            FROM forum.forum_flights
          ) u
          WHERE nullif(btrim(airport), '') IS NOT NULL
            AND nullif(btrim(country), '') IS NOT NULL
          GROUP BY upper(btrim(airport)), btrim(country)
        ) ranked
        WHERE rn = 1
        """
    )
    log(f"   airport_country: {rowcount(status)}")
