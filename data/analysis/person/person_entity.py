"""
Итоговые сущности для отчёта:
  feat.person  — пользователь (ДР, ФИО, паспорта, карты)
  feat.flight  — каталог рейсов (люди на рейсе, страны, источники)

Карты/якоря для сборки остаются в stage.*; в feat больше нет person_card / person_anchor.
"""

from __future__ import annotations

import asyncpg

from data.analysis.db import rowcount
from data.analysis.person.util import log


async def build_person_entity(conn: asyncpg.Connection) -> None:
    """Одна строка feat.person на каждого person_features."""
    log("12) feat.person (сущность пользователя)…")
    status = await conn.execute(
        """
        INSERT INTO feat.person (
          person_id, birth_date,
          name_forum, name_pointz, name_sirena,
          doc_passport_rf, doc_passport_foreign, cards
        )
        WITH names AS (
          SELECT
            person_id,
            nullif(btrim(split_part(coalesce(names_forum, ''), ' | ', 1)), '') AS name_forum,
            nullif(btrim(split_part(coalesce(names_pointz, ''), ' | ', 1)), '') AS name_pointz,
            nullif(btrim(split_part(coalesce(names_sirena, ''), ' | ', 1)), '') AS name_sirena
          FROM feat.person_evidence
        ),
        cards AS (
          SELECT
            person_id,
            string_agg(card_key, ' | ' ORDER BY card_key) AS cards
          FROM stage.card_person
          GROUP BY person_id
        ),
        docs_raw AS (
          -- traveldoc через FF# → card
          SELECT
            cp.person_id,
            upper(regexp_replace(btrim(s.traveldoc), '[^0-9A-Za-z]', '', 'g')) AS doc_key,
            length(regexp_replace(btrim(s.traveldoc), '[^0-9]', '', 'g')) AS ndigits
          FROM skyteam.sirena_records s
          JOIN stage.card_person cp
            ON cp.card_key = meta.norm_loyalty_card(
                 upper(substring(s.paxadditionalinfo from 'FF#([A-Za-z]{2})')),
                 substring(s.paxadditionalinfo
                           from 'FF#[A-Za-z]{2}[[:space:]]*([0-9]+)')
               )
          WHERE s.paxadditionalinfo ~ 'FF#[A-Za-z]{2}'
            AND coalesce(btrim(s.traveldoc), '') NOT IN ('', 'N/A')

          UNION

          -- traveldoc через якорь sirena_doc (без FF#)
          SELECT
            pa.person_id,
            pa.anchor_key AS doc_key,
            length(regexp_replace(pa.anchor_key, '[^0-9]', '', 'g')) AS ndigits
          FROM stage.person_anchor pa
          WHERE pa.anchor_type = 'sirena_doc'
        ),
        docs AS (
          SELECT
            person_id,
            string_agg(DISTINCT doc_key, ' | ' ORDER BY doc_key)
              FILTER (WHERE ndigits = 10) AS doc_rf,
            string_agg(DISTINCT doc_key, ' | ' ORDER BY doc_key)
              FILTER (WHERE ndigits = 9) AS doc_fg
          FROM docs_raw
          WHERE length(doc_key) > 0
          GROUP BY person_id
        ),
        dobs AS (
          SELECT person_id, dob::date AS birth_date
          FROM (
            SELECT
              person_id,
              dob,
              row_number() OVER (
                PARTITION BY person_id
                ORDER BY cnt DESC, dob
              ) AS rn
            FROM (
              SELECT
                x.person_id,
                s.paxbirthdate AS dob,
                count(*) AS cnt
              FROM (
                SELECT cp.person_id, s.sirena_record_pk
                FROM skyteam.sirena_records s
                JOIN stage.card_person cp
                  ON cp.card_key = meta.norm_loyalty_card(
                       upper(substring(s.paxadditionalinfo from 'FF#([A-Za-z]{2})')),
                       substring(s.paxadditionalinfo
                                 from 'FF#[A-Za-z]{2}[[:space:]]*([0-9]+)')
                     )
                WHERE s.paxadditionalinfo ~ 'FF#[A-Za-z]{2}'
                  AND s.paxbirthdate ~ '^\\d{4}-\\d{2}-\\d{2}$'

                UNION

                SELECT pa.person_id, s.sirena_record_pk
                FROM skyteam.sirena_records s
                JOIN stage.person_anchor pa
                  ON pa.anchor_type = 'sirena_doc'
                 AND pa.anchor_key = upper(
                       regexp_replace(btrim(s.traveldoc), '[^0-9A-Za-z]', '', 'g')
                     )
                WHERE NOT (coalesce(s.paxadditionalinfo, '') ~ 'FF#[A-Za-z]{2}')
                  AND s.paxbirthdate ~ '^\\d{4}-\\d{2}-\\d{2}$'
              ) x
              JOIN skyteam.sirena_records s ON s.sirena_record_pk = x.sirena_record_pk
              GROUP BY x.person_id, s.paxbirthdate
            ) agg
          ) ranked
          WHERE rn = 1
        )
        SELECT
          f.person_id,
          dobs.birth_date,
          n.name_forum,
          n.name_pointz,
          n.name_sirena,
          docs.doc_rf,
          docs.doc_fg,
          cards.cards
        FROM feat.person_features f
        LEFT JOIN names n USING (person_id)
        LEFT JOIN cards USING (person_id)
        LEFT JOIN docs USING (person_id)
        LEFT JOIN dobs USING (person_id)
        """
    )
    log(f"   строк: {rowcount(status)}")


async def build_flight_catalog(conn: asyncpg.Connection) -> None:
    """Каталог физических рейсов: люди, страны, источники."""
    log("13) feat.flight (каталог рейсов)…")
    status = await conn.execute(
        """
        INSERT INTO feat.flight (
          flight_date, flight_number, from_airport, to_airport,
          from_country, to_country, people_n, sources
        )
        WITH people AS (
          SELECT
            flight_date,
            flight_number,
            coalesce(from_airport, '') AS from_airport,
            coalesce(to_airport, '') AS to_airport,
            count(DISTINCT person_id)::int AS people_n,
            min(from_country) AS from_country,
            min(to_country) AS to_country
          FROM stage.flight_unique
          GROUP BY 1, 2, 3, 4
        ),
        srcs AS (
          SELECT
            flight_date,
            flight_number,
            coalesce(from_airport, '') AS from_airport,
            coalesce(to_airport, '') AS to_airport,
            string_agg(DISTINCT src, ' | ' ORDER BY src) AS sources
          FROM stage.flight_event
          GROUP BY 1, 2, 3, 4
        )
        SELECT
          p.flight_date,
          p.flight_number,
          p.from_airport,
          p.to_airport,
          p.from_country,
          p.to_country,
          p.people_n,
          s.sources
        FROM people p
        LEFT JOIN srcs s USING (flight_date, flight_number, from_airport, to_airport)
        """
    )
    log(f"   рейсов: {rowcount(status)}")
    mx = await conn.fetchval("SELECT max(people_n) FROM feat.flight")
    ge100 = await conn.fetchval(
        "SELECT count(*) FROM feat.flight WHERE people_n >= 100"
    )
    log(f"   max people на 1 рейсе: {mx}; ≥100 человек: {ge100}")
