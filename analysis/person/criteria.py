"""
Критерии подозрительности.

Числа → feat.person_features
Списки id → feat.person_evidence (только если критерий > 0; иначе NULL — это норма)

Большие SQL лежат в sql/build/*.sql (подсветка IDE).
"""

from __future__ import annotations

import asyncpg

from analysis import config
from analysis.db import execute_script, rowcount
from analysis.person.util import log
from analysis.sql_load import load_sql


async def compute_high_freq(conn: asyncpg.Connection) -> None:
    """Высокая частота: max_30d + непересекающиеся пики; evidence по пикам."""
    log("6) high_freq…")
    w = config.WINDOW_DAYS_30
    await execute_script(
        conn,
        load_sql(
            "high_freq.sql",
            THR=config.HIGH_FREQ_MIN_FLIGHTS_30D,
            W_MINUS_1=w - 1,
            GAP=config.HIGH_FREQ_PEAK_GAP_DAYS,
        ),
    )
    # language=SQL
    status = await conn.execute(
        """
        UPDATE feat.person_features f SET
          high_freq_windows_n = h.windows_n,
          high_freq_max_flights_30d = h.max_30d
        FROM stage.high_freq_windows h WHERE f.person_id = h.person_id
        """
    )
    await conn.execute(
        load_sql(
            "evidence_from_peaks.sql",
            PREFIX="high_freq",
            PEAKS_TABLE="stage.high_freq_peaks",
            WINDOWS_TABLE="stage.high_freq_windows",
        )
    )
    log(f"   people: {rowcount(status)}")


async def compute_spike(conn: asyncpg.Connection) -> None:
    """Всплеск: непересекающиеся окна; evidence по пикам."""
    log("7) spike…")
    w = config.WINDOW_DAYS_30
    await execute_script(
        conn,
        load_sql(
            "spike.sql",
            MIN_NOW=config.SPIKE_MIN_NOW,
            RATIO=config.SPIKE_MIN_RATIO,
            W=w,
            W_MINUS_1=w - 1,
            GAP=config.SPIKE_PEAK_GAP_DAYS,
        ),
    )
    # language=SQL
    status = await conn.execute(
        """
        UPDATE feat.person_features f SET spike_windows_n = s.windows_n
        FROM stage.spike_windows s WHERE f.person_id = s.person_id
        """
    )
    await conn.execute(
        load_sql(
            "evidence_from_peaks.sql",
            PREFIX="spike",
            PEAKS_TABLE="stage.spike_peaks",
            WINDOWS_TABLE="stage.spike_windows",
        )
    )
    log(f"   people: {rowcount(status)}")


async def compute_route_gap_and_quick_return(conn: asyncpg.Connection) -> None:
    """Разрыв маршрута и туда-обратно."""
    log("8) route_gap + quick_return…")
    ignore = ", ".join(f"'{a}'" for a in config.ROUTE_IGNORE_AIRPORTS)
    await execute_script(conn, load_sql("route_seq.sql", IGNORE=ignore))
    await execute_script(conn, load_sql("route_gap.sql"))
    await execute_script(
        conn, load_sql("quick_return.sql", QD=config.QUICK_RETURN_MAX_DAYS)
    )

    for feat_col, stage_tbl, pref in (
        ("route_gap_n", "stage.route_gap", "route_gap"),
        ("quick_return_n", "stage.quick_return", "quick_return"),
    ):
        # language=SQL
        await conn.execute(
            f"""
            UPDATE feat.person_features f SET {feat_col} = s.n
            FROM (SELECT person_id, count(*) AS n FROM {stage_tbl} GROUP BY 1) s
            WHERE f.person_id = s.person_id
            """
        )
        await conn.execute(
            load_sql("pair_evidence.sql", PREFIX=pref, STAGE_TBL=stage_tbl)
        )
    log("   ready")


async def compute_flight_conflict(conn: asyncpg.Connection) -> None:
    """Конфликт маршрутов между источниками на одну дату+рейс."""
    log("9) flight_conflict…")
    await execute_script(conn, load_sql("flight_conflict.sql"))
    # language=SQL
    await conn.execute(
        """
        UPDATE feat.person_features f SET flight_conflict_n = c.n
        FROM stage.flight_conflict c WHERE f.person_id = c.person_id
        """
    )
    # language=SQL
    status = await conn.execute(
        """
        UPDATE feat.person_evidence e SET
          flight_conflict_skyteam_flight_ids = c.sky,
          flight_conflict_forum_flight_ids = c.frm,
          flight_conflict_pointz_activity_ids = c.ptz,
          flight_conflict_sirena_record_ids = c.sir
        FROM stage.flight_conflict c WHERE e.person_id = c.person_id
        """
    )
    log(f"   people: {rowcount(status)}")


async def compute_name_doc_multi(conn: asyncpg.Connection) -> None:
    """Имена, документы Sirena, карта у нескольких профилей."""
    log("10) name / doc / card_multi…")

    # language=SQL
    await conn.execute(
        """
        UPDATE feat.person_features SET
          name_conflict_n = GREATEST(names_distinct_n - 1, 0)
        WHERE names_distinct_n > 1
        """
    )
    # language=SQL
    await conn.execute(
        """
        UPDATE feat.person_evidence e SET
          name_conflict_forum_profile_ids =
            CASE WHEN f.name_conflict_n > 0 THEN e.forum_profile_ids END,
          name_conflict_pointz_user_ids =
            CASE WHEN f.name_conflict_n > 0 THEN e.pointz_user_ids END
        FROM feat.person_features f
        WHERE e.person_id = f.person_id AND f.name_conflict_n > 0
        """
    )
    # language=SQL
    await conn.execute(
        """
        UPDATE feat.person_evidence e SET name_conflict_sirena_record_ids = s.ids
        FROM (
          WITH mapped AS (
            SELECT DISTINCT person_id, src_id
            FROM (
              SELECT
                cp.person_id,
                r.sirena_record_pk::text AS src_id
              FROM skyteam.sirena_records r
              JOIN stage.card_person cp
                ON cp.card_key = meta.norm_loyalty_card(
                     upper(substring(r.paxadditionalinfo from 'FF#([A-Za-z]{2})')),
                     substring(r.paxadditionalinfo
                               from 'FF#[A-Za-z]{2}[[:space:]]*([0-9]+)')
                   )
              WHERE r.paxadditionalinfo ~ 'FF#[A-Za-z]{2}'
                AND nullif(btrim(r.paxname), '') IS NOT NULL

              UNION

              SELECT
                pa.person_id,
                r.sirena_record_pk::text AS src_id
              FROM skyteam.sirena_records r
              JOIN stage.person_anchor pa
                ON pa.anchor_type = 'sirena_doc'
               AND pa.anchor_key = upper(
                     regexp_replace(btrim(r.traveldoc), '[^0-9A-Za-z]', '', 'g')
                   )
              WHERE coalesce(btrim(r.traveldoc), '') NOT IN ('', 'N/A')
                AND NOT (coalesce(r.paxadditionalinfo, '') ~ 'FF#[A-Za-z]{2}')
                AND nullif(btrim(r.paxname), '') IS NOT NULL
            ) u
          )
          SELECT person_id,
                 string_agg(src_id, ' | ' ORDER BY src_id::bigint) AS ids
          FROM mapped
          GROUP BY person_id
        ) s
        JOIN feat.person_features f ON f.person_id = s.person_id AND f.name_conflict_n > 0
        WHERE e.person_id = s.person_id
        """
    )

    await execute_script(conn, load_sql("doc_conflict.sql"))
    # language=SQL
    await conn.execute(
        """
        UPDATE feat.person_features f SET
          doc_rf_conflict_n      = greatest(d.n_rf - 1, 0),
          doc_foreign_conflict_n = greatest(d.n_foreign - 1, 0),
          doc_other_conflict_n   = greatest(d.n_other - 1, 0)
        FROM stage.doc_conflict d
        WHERE f.person_id = d.person_id
        """
    )
    # language=SQL
    await conn.execute(
        """
        UPDATE feat.person_evidence e SET
          doc_rf_conflict_sirena_record_ids =
            CASE WHEN d.n_rf > 1 THEN d.rf_ids END,
          doc_foreign_conflict_sirena_record_ids =
            CASE WHEN d.n_foreign > 1 THEN d.foreign_ids END,
          doc_other_conflict_sirena_record_ids =
            CASE WHEN d.n_other > 1 THEN d.other_ids END
        FROM stage.doc_conflict d
        WHERE e.person_id = d.person_id
        """
    )

    await execute_script(conn, load_sql("card_multi.sql"))
    # language=SQL
    await conn.execute(
        """
        UPDATE feat.person_features f SET card_multi_profile_n = m.n
        FROM stage.card_multi m WHERE f.person_id = m.person_id
        """
    )
    # language=SQL
    await conn.execute(
        """
        UPDATE feat.person_evidence e SET
          card_multi_forum_profile_ids = m.forum_ids,
          card_multi_pointz_user_ids = m.pointz_ids
        FROM stage.card_multi m WHERE e.person_id = m.person_id
        """
    )
    # детали аномалии «карта у нескольких аккаунтов» — отдельная таблица
    await execute_script(conn, load_sql("card_conflict.sql"))
    n_conf = await conn.fetchval("SELECT count(*) FROM feat.card_conflict")
    log(f"   card_conflict cards: {n_conf}")
    log("   ready")


async def _run_route_tail_band(
    conn: asyncpg.Connection,
    *,
    ignore: str,
    rmin: int,
    rmax: int,
    rep: int,
    legs_table: str,
    agg_table: str,
    feat_col: str,
    evid_prefix: str,
) -> int:
    """Один прогон хвоста (средние или редкие OD) → stage + feat."""
    await execute_script(
        conn,
        load_sql(
            "route_tail_legs.sql",
            LEGS_TABLE=legs_table,
            AGG_TABLE=agg_table,
            IGNORE=ignore,
            RMIN=rmin,
            RMAX=rmax,
            DMIN=config.SHADOW_DELAY_MIN_DAYS,
            DMAX=config.SHADOW_DELAY_MAX_DAYS,
        ),
    )
    await execute_script(
        conn,
        load_sql(
            "route_tail_agg.sql",
            LEGS_TABLE=legs_table,
            AGG_TABLE=agg_table,
            FEAT_COL=feat_col,
            EVID_PREFIX=evid_prefix,
            REP=rep,
        ),
    )
    return int(await conn.fetchval(f"SELECT count(*) FROM {agg_table}"))


async def compute_route_tail(conn: asyncpg.Connection) -> None:
    """Хвост: средние OD → route_tail_n; редкие → route_tail_rare_n."""
    log("11) route_tail…")
    ignore = ", ".join(f"'{a}'" for a in config.ROUTE_IGNORE_AIRPORTS)
    n = await _run_route_tail_band(
        conn,
        ignore=ignore,
        rmin=config.SHADOW_ROUTE_MIN_FLIGHTS,
        rmax=config.SHADOW_ROUTE_MAX_FLIGHTS,
        rep=config.SHADOW_MIN_REPEATS,
        legs_table="stage.route_tail_leg",
        agg_table="stage.route_tail",
        feat_col="route_tail_n",
        evid_prefix="route_tail",
    )
    log(f"   medium people: {n}")
    n_rare = await _run_route_tail_band(
        conn,
        ignore=ignore,
        rmin=config.SHADOW_RARE_ROUTE_MIN_FLIGHTS,
        rmax=config.SHADOW_RARE_ROUTE_MAX_FLIGHTS,
        rep=config.SHADOW_RARE_MIN_REPEATS,
        legs_table="stage.route_tail_leg_rare",
        agg_table="stage.route_tail_rare",
        feat_col="route_tail_rare_n",
        evid_prefix="route_tail_rare",
    )
    log(f"   rare people:   {n_rare}")


async def print_summary(conn: asyncpg.Connection) -> None:
    """Сводка после сборки."""
    n = await conn.fetchval("SELECT count(*) FROM feat.person_features")
    row = await conn.fetchrow(
        """
        SELECT
          count(*) FILTER (WHERE high_freq_windows_n > 0),
          count(*) FILTER (WHERE spike_windows_n > 0),
          count(*) FILTER (WHERE route_gap_n > 0),
          count(*) FILTER (WHERE quick_return_n > 0),
          count(*) FILTER (WHERE flight_conflict_n > 0),
          count(*) FILTER (WHERE name_conflict_n > 0),
          count(*) FILTER (WHERE doc_rf_conflict_n > 0),
          count(*) FILTER (WHERE doc_foreign_conflict_n > 0),
          count(*) FILTER (WHERE doc_other_conflict_n > 0),
          count(*) FILTER (WHERE card_multi_profile_n > 0),
          count(*) FILTER (WHERE route_tail_n > 0),
          count(*) FILTER (WHERE route_tail_rare_n > 0),
          count(*) FILTER (WHERE cards_n > 1),
          count(*) FILTER (WHERE identity_kind = 'card'),
          count(*) FILTER (WHERE identity_kind = 'flight_match'),
          count(*) FILTER (WHERE identity_kind = 'forum_profile'),
          count(*) FILTER (WHERE identity_kind = 'sirena_doc'),
          count(*) FILTER (WHERE NOT identity_resolved)
        FROM feat.person_features
        """
    )
    log("\n=== feat.person_features ===")
    log(f"  человек:             {n}")
    log(f"  identity card:       {row[13]}")
    log(f"  identity flight_match: {row[14]}")
    log(f"  identity forum_only: {row[15]}")
    log(f"  identity sirena_doc: {row[16]}")
    log(f"  unresolved (нет паспорта): {row[17]}")
    log(f"  с >1 картой:         {row[12]}")
    log(f"  high_freq > 0:       {row[0]}")
    log(f"  spike > 0:           {row[1]}")
    log(f"  route_gap > 0:       {row[2]}")
    log(f"  quick_return > 0:    {row[3]}")
    log(f"  flight_conflict > 0: {row[4]}")
    log(f"  name_conflict > 0:   {row[5]}")
    log(f"  doc_rf > 0:          {row[6]}")
    log(f"  doc_foreign > 0:     {row[7]}")
    log(f"  doc_other > 0:       {row[8]}")
    log(f"  card_multi > 0:      {row[9]}")
    log(f"  route_tail > 0:      {row[10]}")
    log(f"  route_tail_rare > 0: {row[11]}")
    log(f"  evidence:            {await conn.fetchval('SELECT count(*) FROM feat.person_evidence')}")
    log(f"  person (сущность):   {await conn.fetchval('SELECT count(*) FROM feat.person')}")
    log(f"  flight (каталог):    {await conn.fetchval('SELECT count(*) FROM feat.flight')}")
    log(f"  card_conflict:       {await conn.fetchval('SELECT count(*) FROM feat.card_conflict')}")
    log(f"  flight_match assigned: "
        f"{await conn.fetchval('SELECT count(*) FROM stage.flight_match WHERE assigned')}")
    log(f"  route_tail_leg:      {await conn.fetchval('SELECT count(*) FROM stage.route_tail_leg')}")
    log(
        f"  route_tail_leg_rare: "
        f"{await conn.fetchval('SELECT count(*) FROM stage.route_tail_leg_rare')}"
    )
