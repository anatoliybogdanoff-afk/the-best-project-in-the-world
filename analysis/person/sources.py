"""
Где лежат сырые таблицы после раскладки по схемам источников.

forum.* / skyteam.* / pointz.*  — сырьё
stage.*                         — промежуточные таблицы сборки (можно смотреть)
feat.*                          — витрины для модели и проверки
"""

from __future__ import annotations

import asyncpg

from analysis.person.util import log

# старое имя в public → (схема, имя таблицы)  — для переноса уже загруженной БД
PUBLIC_TO_SOURCE: list[tuple[str, str, str]] = [
    ("forum_profiles", "forum", "forum_profiles"),
    ("forum_documents", "forum", "forum_documents"),
    ("forum_cards", "forum", "forum_cards"),
    ("forum_flights", "forum", "forum_flights"),
    ("skyteam_flights", "skyteam", "skyteam_flights"),
    ("skyteam_flight_cards", "skyteam", "skyteam_flight_cards"),
    ("timetable_records", "skyteam", "timetable_records"),
    ("sirena_records", "skyteam", "sirena_records"),
    ("boarding_passes", "skyteam", "boarding_passes"),
    ("boarding_data", "skyteam", "boarding_data"),
    ("pointz_users", "pointz", "pointz_users"),
    ("pointz_cards", "pointz", "pointz_cards"),
    ("pointz_activities", "pointz", "pointz_activities"),
    ("pointz_errors", "pointz", "pointz_errors"),
]

# суррогатные PK: (schema, table, column)
ROW_ID_COLUMNS: list[tuple[str, str, str]] = [
    ("forum", "forum_flights", "forum_flight_id"),
    ("forum", "forum_cards", "forum_card_id"),
    ("forum", "forum_documents", "forum_document_id"),
    ("forum", "forum_profiles", "forum_profile_pk"),
    ("skyteam", "skyteam_flights", "skyteam_flight_pk"),
    ("skyteam", "skyteam_flight_cards", "skyteam_flight_card_id"),
    ("skyteam", "sirena_records", "sirena_record_pk"),
    ("skyteam", "boarding_passes", "boarding_pass_id"),
    ("skyteam", "boarding_data", "boarding_data_id"),
    ("pointz", "pointz_activities", "pointz_activity_pk"),
    ("pointz", "pointz_cards", "pointz_card_pk"),
    ("pointz", "pointz_users", "pointz_user_pk"),
]


async def ensure_source_schemas(conn: asyncpg.Connection) -> None:
    """Создаёт схемы forum / skyteam / pointz / stage, если их ещё нет."""
    for schema, comment in (
        ("forum", "FrequentFlyer Forum"),
        ("skyteam", "SkyTeam + timetable/sirena/boarding"),
        ("pointz", "Pointz Aggregator"),
        ("stage", "Промежуточные таблицы сборки (не TEMP)"),
    ):
        await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        # COMMENT … IS не принимает bind-параметры в prepared statement
        safe = comment.replace("'", "''")
        await conn.execute(f"COMMENT ON SCHEMA {schema} IS '{safe}'")


async def relocate_public_tables_if_needed(conn: asyncpg.Connection) -> None:
    """
    Если таблицы ещё лежат в public (старый docker-load) — переносит в схемы источников.

    На новой установке (01_schema уже с forum/skyteam/pointz) ничего не делает.
    """
    log("0a) Раскладка public → forum/skyteam/pointz (если нужно)…")
    await ensure_source_schemas(conn)
    moved = 0
    for old_name, schema, new_name in PUBLIC_TO_SOURCE:
        exists = await conn.fetchval(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = $1
            """,
            old_name,
        )
        if not exists:
            continue
        target = await conn.fetchval(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = $1 AND table_name = $2
            """,
            schema,
            new_name,
        )
        if target:
            log(f"   skip {old_name}: уже есть {schema}.{new_name}")
            continue
        await conn.execute(f'ALTER TABLE public."{old_name}" SET SCHEMA {schema}')
        if old_name != new_name:
            await conn.execute(
                f'ALTER TABLE {schema}."{old_name}" RENAME TO "{new_name}"'
            )
        log(f"   moved public.{old_name} → {schema}.{new_name}")
        moved += 1
    log(f"   перенесено таблиц: {moved}")
