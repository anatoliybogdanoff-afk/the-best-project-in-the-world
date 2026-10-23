"""
Пассажиры без карт лояльности.

1) Карточный контур не трогаем.
2) Sirena без FF# идентифицируем по нормализованному traveldoc (якорь sirena_doc).
3) Forum↔Sirena: ≥ CARDLESS_MIN_SHARED_LEGS общих рейсов + unique best;
   при ничьей — мягко: одинаковая валидная ДР (часто РФ+загран), затем ФИО.
4) Если паспорт не найден — person всё равно создаём, identity_resolved=false.

Якоря пишем только в stage.person_anchor (для сборки рейсов).
Сущность пользователя для отчёта — feat.person (см. person_entity.py).
"""

from __future__ import annotations

import re
from collections import defaultdict

import asyncpg

from analysis import config
from analysis.db import execute_script, rowcount
from analysis.person.util import join_ids, log
from analysis.sql_load import load_sql

_FIO_SPLIT = re.compile(r"[^0-9A-Za-zА-Яа-яЁё]+", re.UNICODE)


def _fio_tokens(name: str | None) -> set[str]:
    if not name:
        return set()
    return {t for t in _FIO_SPLIT.split(name.upper()) if len(t) >= 2}


def _fio_jaccard(a: str | None, b: str | None) -> float:
    ta, tb = _fio_tokens(a), _fio_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


async def build_cardless_persons(conn: asyncpg.Connection) -> None:
    """После card-person: матчинг, новые строки feat.*, якоря stage.person_anchor."""
    log("4b) Cardless: doc_on_card + flight_match + новые person_id…")
    await _fill_doc_on_card(conn)
    await _anchor_docs_already_on_cards(conn)
    await execute_script(
        conn,
        load_sql(
            "cardless_match.sql",
            MIN_SHARED=config.CARDLESS_MIN_SHARED_LEGS,
        ),
    )
    soft_n = await _resolve_soft_ties(conn)
    log(f"   soft-assign (DOB/FIO): {soft_n}")

    n_assigned = await conn.fetchval(
        "SELECT count(*) FROM stage.flight_match WHERE assigned"
    )
    n_to_card = await conn.fetchval(
        """
        SELECT count(*) FROM stage.flight_match
        WHERE assigned AND target_person_id IS NOT NULL
        """
    )
    log(
        f"   матчей assigned≥{config.CARDLESS_MIN_SHARED_LEGS}: {n_assigned}"
        f" (из них в существующий card-person: {n_to_card})"
    )

    next_pid = await _merge_matches_into_cards(conn)
    next_pid = await _create_flight_match_persons(conn, next_pid)
    next_pid = await _create_unmatched_forum_persons(conn, next_pid)
    next_pid = await _create_orphan_sirena_persons(conn, next_pid)

    await _bump_person_id_seq(conn)

    kinds = await conn.fetch(
        """
        SELECT identity_kind, identity_resolved, count(*)
        FROM feat.person_features
        GROUP BY 1, 2
        ORDER BY 1, 2
        """
    )
    for kind, resolved, n in kinds:
        log(f"   identity {kind} resolved={resolved}: {n}")
    log(f"   person_anchor: {await conn.fetchval('SELECT count(*) FROM stage.person_anchor')}")
    log(f"   next free person_id would be {next_pid}")


async def _fill_doc_on_card(conn: asyncpg.Connection) -> None:
    """traveldoc с FF#-строк → уже известный card person_id (если однозначен)."""
    status = await conn.execute(
        """
        INSERT INTO stage.doc_on_card (doc_key, person_id)
        SELECT doc_key, min(person_id)
        FROM (
          SELECT
            upper(regexp_replace(btrim(s.traveldoc), '[^0-9A-Za-z]', '', 'g')) AS doc_key,
            cp.person_id
          FROM skyteam.sirena_records s
          JOIN stage.card_person cp
            ON cp.card_key = meta.norm_loyalty_card(
                 upper(substring(s.paxadditionalinfo from 'FF#([A-Za-z]{2})')),
                 substring(s.paxadditionalinfo
                           from 'FF#[A-Za-z]{2}[[:space:]]*([0-9]+)')
               )
          WHERE s.paxadditionalinfo ~ 'FF#[A-Za-z]{2}'
            AND coalesce(btrim(s.traveldoc), '') NOT IN ('', 'N/A')
        ) t
        WHERE length(doc_key) > 0
        GROUP BY doc_key
        HAVING count(DISTINCT person_id) = 1
        """
    )
    log(f"   doc_on_card: {rowcount(status)}")


async def _anchor_docs_already_on_cards(conn: asyncpg.Connection) -> None:
    """No-FF рейсы с тем же паспортом, что у card-person, не плодят нового человека."""
    status = await conn.execute(
        """
        INSERT INTO stage.person_anchor (person_id, anchor_type, anchor_key)
        SELECT person_id, 'sirena_doc', doc_key
        FROM stage.doc_on_card
        ON CONFLICT DO NOTHING
        """
    )
    log(f"   sirena_doc → card-person: {rowcount(status)}")


async def _resolve_soft_ties(conn: asyncpg.Connection) -> int:
    """
    Ничьи на лучших ногах (≥ MIN_SHARED), ещё не assigned:

    1) Если у кандидатов одна общая валидная ДР → назначаем все такие doc
       (типичный РФ+загран одного человека). ДР битая/N/A → не используем.
    2) Иначе ФИО (последний приоритет): единственный кандидат с Jaccard ≥ порога
       и строго лучше остальных.
    """
    min_shared = config.CARDLESS_MIN_SHARED_LEGS
    fio_min = config.CARDLESS_FIO_JACCARD_MIN

    profiles = await conn.fetch(
        """
        SELECT DISTINCT m.profile_id, m.shared_legs AS best_shared
        FROM stage.flight_match m
        JOIN (
          SELECT profile_id, max(shared_legs) AS best
          FROM stage.flight_match
          GROUP BY profile_id
        ) b ON b.profile_id = m.profile_id AND b.best = m.shared_legs
        WHERE m.shared_legs >= $1
          AND NOT EXISTS (
            SELECT 1 FROM stage.flight_match x
            WHERE x.profile_id = m.profile_id AND x.assigned
          )
        """,
        min_shared,
    )
    if not profiles:
        return 0

    assigned_n = 0
    for prow in profiles:
        profile_id = prow["profile_id"]
        best = int(prow["best_shared"])
        cands = await conn.fetch(
            """
            SELECT
              m.doc_key,
              m.shared_legs,
              (
                SELECT s.paxbirthdate
                FROM skyteam.sirena_records s
                WHERE upper(regexp_replace(btrim(s.traveldoc), '[^0-9A-Za-z]', '', 'g'))
                      = m.doc_key
                  AND s.paxbirthdate ~ '^\\d{4}-\\d{2}-\\d{2}$'
                GROUP BY s.paxbirthdate
                ORDER BY count(*) DESC, s.paxbirthdate
                LIMIT 1
              ) AS dob,
              (
                SELECT nullif(btrim(s.paxname), '')
                FROM skyteam.sirena_records s
                WHERE upper(regexp_replace(btrim(s.traveldoc), '[^0-9A-Za-z]', '', 'g'))
                      = m.doc_key
                  AND nullif(btrim(s.paxname), '') IS NOT NULL
                LIMIT 1
              ) AS pname,
              (
                SELECT person_id FROM stage.doc_on_card d WHERE d.doc_key = m.doc_key
              ) AS card_pid
            FROM stage.flight_match m
            WHERE m.profile_id = $1 AND m.shared_legs = $2
            """,
            profile_id,
            best,
        )
        if len(cands) < 2:
            continue

        forum_fio = await conn.fetchval(
            """
            SELECT nullif(btrim(coalesce(first_name,'') || ' ' || coalesce(last_name,'')), '')
            FROM forum.forum_profiles WHERE profile_id = $1
            """,
            profile_id,
        )

        by_dob: dict[str, list] = defaultdict(list)
        for c in cands:
            if c["dob"]:
                by_dob[c["dob"]].append(c)

        chosen = None
        # 1) DOB: ровно одна валидная дата покрывает ≥2 doc → все они
        multi_dob = [(d, docs) for d, docs in by_dob.items() if len(docs) >= 2]
        if len(multi_dob) == 1:
            chosen = multi_dob[0][1]
        elif len(multi_dob) == 0 and len(by_dob) == 1 and len(next(iter(by_dob.values()))) >= 2:
            chosen = next(iter(by_dob.values()))

        # 2) FIO last
        if chosen is None and forum_fio:
            scored = [
                (_fio_jaccard(forum_fio, c["pname"]), c) for c in cands
            ]
            scored.sort(key=lambda x: x[0], reverse=True)
            best_s, best_c = scored[0]
            second = scored[1][0] if len(scored) > 1 else 0.0
            if best_s >= fio_min and best_s > second:
                chosen = [best_c]

        if not chosen:
            continue

        # не смешиваем разные card person_id
        card_pids = {c["card_pid"] for c in chosen if c["card_pid"] is not None}
        if len(card_pids) > 1:
            continue
        target = next(iter(card_pids)) if card_pids else None

        for c in chosen:
            await conn.execute(
                """
                UPDATE stage.flight_match
                SET assigned = true,
                    target_person_id = coalesce($3, target_person_id)
                WHERE profile_id = $1 AND doc_key = $2
                """,
                profile_id,
                c["doc_key"],
                target,
            )
        assigned_n += 1

    return assigned_n


async def _merge_matches_into_cards(conn: asyncpg.Connection) -> int:
    """
    assigned + target_person_id: cardless-профиль и no-FF doc → уже карточный человек.
    Добавляем якоря и дописываем evidence.
    """
    rows = await conn.fetch(
        """
        SELECT
          m.profile_id, m.doc_key, m.shared_legs, m.target_person_id AS person_id,
          nullif(btrim(coalesce(p.first_name,'') || ' ' || coalesce(p.last_name,'')), '') AS fio
        FROM stage.flight_match m
        LEFT JOIN forum.forum_profiles p ON p.profile_id = m.profile_id
        WHERE m.assigned AND m.target_person_id IS NOT NULL
        ORDER BY m.profile_id, m.doc_key
        """
    )
    if not rows:
        return int(
            await conn.fetchval(
                "SELECT coalesce(max(person_id), 0) FROM feat.person_features"
            )
        ) + 1

    anchors = []
    for r in rows:
        pid = int(r["person_id"])
        anchors.append((pid, "forum_profile", r["profile_id"]))
        anchors.append((pid, "sirena_doc", r["doc_key"]))

    await conn.executemany(
        """
        INSERT INTO stage.person_anchor (person_id, anchor_type, anchor_key)
        VALUES ($1, $2, $3)
        ON CONFLICT DO NOTHING
        """,
        anchors,
    )

    for r in rows:
        pid = int(r["person_id"])
        await conn.execute(
            """
            UPDATE feat.person_evidence e SET
              forum_profile_ids = CASE
                WHEN e.forum_profile_ids IS NULL OR e.forum_profile_ids = '' THEN $2
                WHEN position($2 in e.forum_profile_ids) > 0 THEN e.forum_profile_ids
                ELSE e.forum_profile_ids || ' | ' || $2
              END,
              sirena_docs = CASE
                WHEN e.sirena_docs IS NULL OR e.sirena_docs = '' THEN $3
                WHEN position($3 in e.sirena_docs) > 0 THEN e.sirena_docs
                ELSE e.sirena_docs || ' | ' || $3
              END,
              names_forum = CASE
                WHEN $4::text IS NULL THEN e.names_forum
                WHEN e.names_forum IS NULL OR e.names_forum = '' THEN $4
                WHEN position($4 in e.names_forum) > 0 THEN e.names_forum
                ELSE e.names_forum || ' | ' || $4
              END
            WHERE e.person_id = $1
            """,
            pid,
            r["profile_id"],
            r["doc_key"],
            r["fio"],
        )
        await conn.execute(
            """
            UPDATE feat.person_features f SET
              match_shared_legs = GREATEST(f.match_shared_legs, $2),
              names_distinct_n = (
                SELECT count(DISTINCT n) FROM (
                  SELECT unnest(string_to_array(nullif(e.names_forum, ''), ' | ')) AS n
                  FROM feat.person_evidence e WHERE e.person_id = f.person_id
                  UNION
                  SELECT unnest(string_to_array(nullif(e.names_pointz, ''), ' | '))
                  FROM feat.person_evidence e WHERE e.person_id = f.person_id
                  UNION
                  SELECT unnest(string_to_array(nullif(e.names_sirena, ''), ' | '))
                  FROM feat.person_evidence e WHERE e.person_id = f.person_id
                ) x WHERE nullif(btrim(n), '') IS NOT NULL
              )
            FROM feat.person_evidence e
            WHERE f.person_id = $1 AND e.person_id = f.person_id
            """,
            pid,
            int(r["shared_legs"]),
        )

    log(f"   влито в card-person: {len(rows)} профилей")
    return int(
        await conn.fetchval("SELECT coalesce(max(person_id), 0) FROM feat.person_features")
    ) + 1


async def _create_flight_match_persons(
    conn: asyncpg.Connection, next_pid: int
) -> int:
    """Новые люди: assigned profile↔doc(и), документ ещё не на карте. Несколько doc → один person."""
    rows = await conn.fetch(
        """
        SELECT
          m.profile_id,
          m.doc_key,
          m.shared_legs,
          nullif(btrim(coalesce(p.first_name,'') || ' ' || coalesce(p.last_name,'')), '')
            AS fio_forum,
          (
            SELECT nullif(btrim(s.paxname), '')
            FROM skyteam.sirena_records s
            WHERE upper(regexp_replace(btrim(s.traveldoc), '[^0-9A-Za-z]', '', 'g'))
                  = m.doc_key
              AND nullif(btrim(s.paxname), '') IS NOT NULL
            LIMIT 1
          ) AS fio_sirena
        FROM stage.flight_match m
        LEFT JOIN forum.forum_profiles p ON p.profile_id = m.profile_id
        WHERE m.assigned
          AND m.target_person_id IS NULL
        ORDER BY m.profile_id, m.doc_key
        """
    )
    by_prof: dict[str, list] = defaultdict(list)
    used_docs: set[str] = set()
    for r in rows:
        doc = r["doc_key"]
        if doc in used_docs:
            continue
        # doc уже якорь у кого-то — не создаём второго человека
        exists = await conn.fetchval(
            """
            SELECT 1 FROM stage.person_anchor
            WHERE anchor_type = 'sirena_doc' AND anchor_key = $1
            """,
            doc,
        )
        if exists:
            continue
        used_docs.add(doc)
        by_prof[r["profile_id"]].append(r)

    feat_rows = []
    evid_rows = []
    anchors = []
    pid = next_pid
    for prof, docs in by_prof.items():
        # профиль уже якорь
        if await conn.fetchval(
            """
            SELECT 1 FROM stage.person_anchor
            WHERE anchor_type = 'forum_profile' AND anchor_key = $1
            """,
            prof,
        ):
            continue
        shared = max(int(d["shared_legs"]) for d in docs)
        fio_f = docs[0]["fio_forum"]
        fio_s = sorted({d["fio_sirena"] for d in docs if d["fio_sirena"]})
        names = {x for x in [fio_f, *fio_s] if x}
        doc_keys = [d["doc_key"] for d in docs]
        feat_rows.append(
            (pid, "flight_match", True, shared, 0, len(names))
        )
        evid_rows.append(
            (
                pid,
                None,
                join_ids([fio_f] if fio_f else []),
                None,
                join_ids(fio_s),
                prof,
                None,
                join_ids(doc_keys),
            )
        )
        anchors.append((pid, "forum_profile", prof))
        for dk in doc_keys:
            anchors.append((pid, "sirena_doc", dk))
        await conn.execute(
            """
            UPDATE stage.flight_match
            SET target_person_id = $1
            WHERE profile_id = $2 AND assigned AND target_person_id IS NULL
            """,
            pid,
            prof,
        )
        pid += 1

    await _insert_person_batch(conn, feat_rows, evid_rows, anchors)
    log(f"   новых flight_match: {len(feat_rows)}")
    return pid


async def _create_unmatched_forum_persons(
    conn: asyncpg.Connection, next_pid: int
) -> int:
    """Cardless forum без assigned-матча → person с identity_resolved=false."""
    rows = await conn.fetch(
        """
        SELECT
          ff.profile_id,
          nullif(btrim(coalesce(p.first_name,'') || ' ' || coalesce(p.last_name,'')), '') AS fio
        FROM (
          SELECT DISTINCT profile_id
          FROM forum.forum_flights
          WHERE nullif(btrim(profile_id), '') IS NOT NULL
        ) ff
        LEFT JOIN forum.forum_profiles p ON p.profile_id = ff.profile_id
        WHERE NOT EXISTS (
          SELECT 1 FROM forum.forum_cards fc
          WHERE fc.profile_id = ff.profile_id
            AND nullif(btrim(fc.number), '') IS NOT NULL
        )
        AND NOT EXISTS (
          SELECT 1 FROM stage.person_anchor a
          WHERE a.anchor_type = 'forum_profile' AND a.anchor_key = ff.profile_id
        )
        AND NOT EXISTS (
          SELECT 1 FROM stage.flight_match m
          WHERE m.profile_id = ff.profile_id AND m.assigned
        )
        """
    )
    feat_rows = []
    evid_rows = []
    anchors = []
    pid = next_pid
    for r in rows:
        names_n = 1 if r["fio"] else 0
        feat_rows.append((pid, "forum_profile", False, 0, 0, names_n))
        evid_rows.append(
            (
                pid,
                None,
                join_ids([r["fio"]] if r["fio"] else []),
                None,
                None,
                r["profile_id"],
                None,
                None,
            )
        )
        anchors.append((pid, "forum_profile", r["profile_id"]))
        pid += 1

    await _insert_person_batch(conn, feat_rows, evid_rows, anchors)
    log(f"   unresolved forum_profile: {len(feat_rows)}")
    return pid


async def _create_orphan_sirena_persons(
    conn: asyncpg.Connection, next_pid: int
) -> int:
    """
    traveldoc без FF#, не на карте и не в assigned-матче → отдельный sirena_doc person.
    Паспорт есть → identity_resolved=true.
    """
    rows = await conn.fetch(
        """
        WITH docs AS (
          SELECT DISTINCT
            upper(regexp_replace(btrim(s.traveldoc), '[^0-9A-Za-z]', '', 'g')) AS doc_key
          FROM skyteam.sirena_records s
          WHERE coalesce(btrim(s.traveldoc), '') NOT IN ('', 'N/A')
            AND NOT (coalesce(s.paxadditionalinfo, '') ~ 'FF#[A-Za-z]{2}')
        ),
        orphan AS (
          SELECT d.doc_key
          FROM docs d
          WHERE length(d.doc_key) > 0
            AND NOT EXISTS (
              SELECT 1 FROM stage.doc_on_card c WHERE c.doc_key = d.doc_key
            )
            AND NOT EXISTS (
              SELECT 1 FROM stage.person_anchor a
              WHERE a.anchor_type = 'sirena_doc' AND a.anchor_key = d.doc_key
            )
            AND NOT EXISTS (
              SELECT 1 FROM stage.flight_match m
              WHERE m.doc_key = d.doc_key AND m.assigned
            )
        ),
        names AS (
          SELECT DISTINCT ON (doc_key)
            upper(regexp_replace(btrim(s.traveldoc), '[^0-9A-Za-z]', '', 'g')) AS doc_key,
            nullif(btrim(s.paxname), '') AS fio
          FROM skyteam.sirena_records s
          JOIN orphan o
            ON o.doc_key = upper(
                 regexp_replace(btrim(s.traveldoc), '[^0-9A-Za-z]', '', 'g')
               )
          WHERE nullif(btrim(s.paxname), '') IS NOT NULL
          ORDER BY doc_key, s.sirena_record_pk
        )
        SELECT o.doc_key, n.fio
        FROM orphan o
        LEFT JOIN names n USING (doc_key)
        """
    )
    feat_rows = []
    evid_rows = []
    anchors = []
    pid = next_pid
    for r in rows:
        names_n = 1 if r["fio"] else 0
        feat_rows.append((pid, "sirena_doc", True, 0, 0, names_n))
        evid_rows.append(
            (
                pid,
                None,
                None,
                None,
                join_ids([r["fio"]] if r["fio"] else []),
                None,
                None,
                r["doc_key"],
            )
        )
        anchors.append((pid, "sirena_doc", r["doc_key"]))
        pid += 1

    await _insert_person_batch(conn, feat_rows, evid_rows, anchors)
    log(f"   orphan sirena_doc: {len(feat_rows)}")
    return pid


async def _insert_person_batch(
    conn: asyncpg.Connection,
    feat_rows: list[tuple],
    evid_rows: list[tuple],
    anchors: list[tuple],
) -> None:
    if not feat_rows:
        return
    await conn.executemany(
        """
        INSERT INTO feat.person_features (
          person_id, identity_kind, identity_resolved, match_shared_legs,
          cards_n, names_distinct_n
        ) VALUES ($1, $2, $3, $4, $5, $6)
        """,
        feat_rows,
    )
    await conn.executemany(
        """
        INSERT INTO feat.person_evidence (
          person_id, card_numbers,
          names_forum, names_pointz, names_sirena,
          forum_profile_ids, pointz_user_ids, sirena_docs
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        evid_rows,
    )
    if anchors:
        await conn.executemany(
            """
            INSERT INTO stage.person_anchor (person_id, anchor_type, anchor_key)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            anchors,
        )


async def _bump_person_id_seq(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        SELECT setval(
          pg_get_serial_sequence('feat.person_features', 'person_id'),
          (SELECT coalesce(max(person_id), 1) FROM feat.person_features)
        )
        """
    )
