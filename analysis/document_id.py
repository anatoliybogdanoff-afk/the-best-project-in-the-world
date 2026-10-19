"""
Критерий 5: имена (уже в id_conflict) + документы.

Forum documents пустые → по паспортам форума гипотеза непроверяема.
Sirena: разные traveldoc на одной FF-карте → finding_type=doc_conflict.
"""

from __future__ import annotations

from analysis.config import SEVERITY
from analysis.db import cursor


def summarize() -> dict:
    with cursor() as cur:
        cur.execute(
            """
            SELECT count(*),
                   count(*) FILTER (
                       WHERE coalesce(trim(document_number), '') <> ''
                   )
            FROM forum_documents
            """
        )
        total, nonempty = cur.fetchone()
        cur.execute(
            "SELECT count(*) FROM work.finding WHERE finding_type = 'id_conflict'"
        )
        name_n = cur.fetchone()[0]
        cur.execute(
            """
            SELECT count(*) FROM (
                SELECT 1
                FROM (
                    SELECT
                        upper(substring(paxadditionalinfo from 'FF#([A-Za-z]{2})'))
                            || ' '
                            || substring(
                                paxadditionalinfo
                                from 'FF#[A-Za-z]{2}[[:space:]]*([0-9]+)'
                            ) AS clean_card,
                        nullif(btrim(traveldoc), '') AS doc
                    FROM sirena_records
                    WHERE paxadditionalinfo ~ 'FF#[A-Za-z]{2}'
                      AND coalesce(btrim(traveldoc), '') NOT IN ('', 'N/A')
                ) s
                WHERE clean_card IS NOT NULL AND doc IS NOT NULL
                GROUP BY clean_card
                HAVING count(DISTINCT doc) > 1
            ) x
            """
        )
        sirena_clash = cur.fetchone()[0]
    return {
        "forum_documents_total": total,
        "forum_documents_nonempty": nonempty,
        "name_conflicts_findings": name_n,
        "sirena_multi_doc_cards": sirena_clash,
        "forum_docs_checkable": nonempty > 0,
    }


def run(*, replace: bool = True, limit: int = 500) -> dict:
    summary = summarize()
    sev = SEVERITY["doc_conflict"]
    inserted = 0

    with cursor() as cur:
        if replace:
            cur.execute(
                """
                DELETE FROM work.evidence
                WHERE finding_id IN (
                    SELECT finding_id FROM work.finding
                    WHERE finding_type = 'doc_conflict'
                )
                """
            )
            cur.execute(
                "DELETE FROM work.finding WHERE finding_type = 'doc_conflict'"
            )

        if summary["sirena_multi_doc_cards"] == 0:
            return {**summary, "doc_conflict_inserted": 0}

        cur.execute(
            """
            WITH cards AS (
                SELECT
                    clean_card,
                    string_agg(DISTINCT doc, ' | ' ORDER BY doc) AS docs,
                    count(DISTINCT doc) AS n_docs
                FROM (
                    SELECT
                        upper(substring(paxadditionalinfo from 'FF#([A-Za-z]{2})'))
                            || ' '
                            || substring(
                                paxadditionalinfo
                                from 'FF#[A-Za-z]{2}[[:space:]]*([0-9]+)'
                            ) AS clean_card,
                        nullif(btrim(traveldoc), '') AS doc
                    FROM sirena_records
                    WHERE paxadditionalinfo ~ 'FF#[A-Za-z]{2}'
                      AND coalesce(btrim(traveldoc), '') NOT IN ('', 'N/A')
                ) s
                WHERE clean_card IS NOT NULL AND doc IS NOT NULL
                GROUP BY clean_card
                HAVING count(DISTINCT doc) > 1
            )
            SELECT 'card:' || clean_card, docs, n_docs
            FROM cards c
            WHERE EXISTS (
                SELECT 1 FROM work.passenger p
                WHERE p.passenger_id = 'card:' || c.clean_card
            )
            LIMIT %s
            """,
            (limit,),
        )
        for passenger_id, docs, n_docs in cur.fetchall():
            cur.execute(
                """
                INSERT INTO work.finding (
                    passenger_id, finding_type, title, detail, severity, status
                ) VALUES (
                    %s, 'doc_conflict',
                    'Разные документы на одной карте (Sirena)',
                    %s, %s, 'needs_check'
                )
                RETURNING finding_id
                """,
                (
                    passenger_id,
                    f"На карте {n_docs} разных traveldoc: {docs}. "
                    f"Сначала проверить склейку FF#.",
                    sev,
                ),
            )
            finding_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO work.evidence (finding_id, kind, label)
                VALUES (%s, 'note', %s)
                """,
                (finding_id, f"documents: {docs}"),
            )
            inserted += 1

    return {**summary, "doc_conflict_inserted": inserted}
