#!/usr/bin/env python3
"""
Сверка итоговых витрин feat.* с stage и сырьём.
Запуск:  .venv/bin/python -m scripts.verify_feat
         или  .venv/bin/python scripts/verify_feat.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.db import connect  # noqa: E402


async def main() -> int:
    conn = await connect()
    ok = True

    def fail(msg: str) -> None:
        nonlocal ok
        ok = False
        print(f"FAIL  {msg}")

    def fine(msg: str) -> None:
        print(f"OK    {msg}")

    n_f = await conn.fetchval("SELECT count(*) FROM feat.person_features")
    n_e = await conn.fetchval("SELECT count(*) FROM feat.person_evidence")
    n_p = await conn.fetchval("SELECT count(*) FROM feat.person")
    n_fl = await conn.fetchval("SELECT count(*) FROM feat.flight")
    if n_f != n_e:
        fail(f"features={n_f} evidence={n_e}")
    else:
        fine(f"features=evidence={n_f}")
    if n_f != n_p:
        fail(f"features={n_f} person={n_p}")
    else:
        fine(f"person=features={n_p}")
    fine(f"feat.flight rows={n_fl}")

    orphan = await conn.fetchval(
        """
        SELECT count(*) FROM feat.person_features f
        LEFT JOIN feat.person_evidence e USING (person_id)
        WHERE e.person_id IS NULL
        """
    )
    if orphan:
        fail(f"features without evidence: {orphan}")
    else:
        fine("каждый features имеет evidence")

    # cards в feat.person совпадают со stage.card_person (агрегат)
    mismatch_cards = await conn.fetchval(
        """
        SELECT count(*) FROM (
          SELECT person_id, string_agg(card_key, ' | ' ORDER BY card_key) AS cards
          FROM stage.card_person
          GROUP BY person_id
          EXCEPT
          SELECT person_id, cards FROM feat.person WHERE cards IS NOT NULL
        ) x
        """
    )
    if mismatch_cards:
        fail(f"feat.person.cards ≠ stage.card_person: {mismatch_cards}")
    else:
        fine("feat.person.cards = aggregate(stage.card_person)")

    crowded = await conn.fetchval(
        "SELECT count(*) FROM feat.flight WHERE people_n >= 1000"
    )
    if crowded:
        fail(f"рейсы с ≥1000 people (подозрительно): {crowded}")
    else:
        fine(f"нет рейсов с ≥1000 people (max={await conn.fetchval('SELECT max(people_n) FROM feat.flight')})")

    # flights_n vs stage
    bad_flights = await conn.fetchval(
        """
        SELECT count(*) FROM feat.person_features f
        LEFT JOIN (
          SELECT person_id, count(*) AS n FROM stage.flight_unique GROUP BY 1
        ) u USING (person_id)
        WHERE f.flights_n <> coalesce(u.n, 0)
        """
    )
    if bad_flights:
        fail(f"flights_n mismatch: {bad_flights}")
    else:
        fine("flights_n = count(stage.flight_unique)")

    # criterion >0 ⇒ хотя бы одно evidence поле заполнено
    checks = [
        (
            "high_freq_windows_n",
            "high_freq_from_date IS NULL AND high_freq_skyteam_flight_ids IS NULL "
            "AND high_freq_forum_flight_ids IS NULL AND high_freq_pointz_activity_ids IS NULL "
            "AND high_freq_sirena_record_ids IS NULL",
        ),
        (
            "spike_windows_n",
            "spike_from_date IS NULL AND spike_skyteam_flight_ids IS NULL "
            "AND spike_forum_flight_ids IS NULL AND spike_pointz_activity_ids IS NULL "
            "AND spike_sirena_record_ids IS NULL",
        ),
        (
            "route_gap_n",
            "route_gap_skyteam_flight_ids IS NULL AND route_gap_forum_flight_ids IS NULL "
            "AND route_gap_pointz_activity_ids IS NULL AND route_gap_sirena_record_ids IS NULL",
        ),
        (
            "route_tail_n",
            "route_tail_leader_person_ids IS NULL",
        ),
        (
            "route_tail_rare_n",
            "route_tail_rare_leader_person_ids IS NULL",
        ),
        (
            "doc_rf_conflict_n",
            "doc_rf_conflict_sirena_record_ids IS NULL",
        ),
        (
            "doc_foreign_conflict_n",
            "doc_foreign_conflict_sirena_record_ids IS NULL",
        ),
        (
            "doc_other_conflict_n",
            "doc_other_conflict_sirena_record_ids IS NULL",
        ),
    ]
    for feat, empty in checks:
        n = await conn.fetchval(
            f"""
            SELECT count(*) FROM feat.person_features f
            JOIN feat.person_evidence e USING (person_id)
            WHERE f.{feat} > 0 AND ({empty})
            """
        )
        if n:
            fail(f"{feat}>0 but evidence empty: {n}")
        else:
            fine(f"{feat}>0 ⇒ evidence заполнен")

    # high_freq ids только внутри peaks
    outside = await conn.fetchval(
        """
        WITH ids AS (
          SELECT e.person_id,
                 unnest(string_to_array(e.high_freq_skyteam_flight_ids, ' | ')) AS src_id
          FROM feat.person_evidence e
          WHERE e.high_freq_skyteam_flight_ids IS NOT NULL
        )
        SELECT count(*) FROM ids i
        JOIN stage.flight_event p
          ON p.person_id = i.person_id AND p.src = 'skyteam' AND p.src_id = i.src_id
        WHERE NOT EXISTS (
          SELECT 1 FROM stage.high_freq_peaks pk
          WHERE pk.person_id = i.person_id
            AND p.flight_date BETWEEN pk.window_start AND pk.window_end
        )
        """
    )
    if outside:
        fail(f"high_freq skyteam ids outside peaks: {outside}")
    else:
        fine("high_freq evidence ids ∈ peaks")

    # sample: flights_n сходится с сырьём через card (skyteam only spot-check)
    sample = await conn.fetch(
        """
        SELECT person_id, flights_n FROM feat.person_features
        WHERE flights_n BETWEEN 5 AND 40
        ORDER BY person_id LIMIT 5
        """
    )
    for pid, fn in sample:
        staged = await conn.fetchval(
            "SELECT count(*) FROM stage.flight_unique WHERE person_id = $1", pid
        )
        if staged != fn:
            fail(f"person {pid}: flights_n={fn} stage={staged}")
        else:
            fine(f"sample person {pid}: flights_n={fn} OK")

    # meta function exists
    fn = await conn.fetchval(
        """
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'meta' AND p.proname = 'norm_loyalty_card'
        """
    )
    if not fn:
        fail("meta.norm_loyalty_card отсутствует")
    else:
        fine("meta.norm_loyalty_card есть (схема meta — Functions, не Tables)")

    # card_conflict: все multi-owner карты из сырья должны быть в таблице
    raw_conf = await conn.fetchval(
        """
        WITH f AS (
          SELECT meta.norm_loyalty_card(programm, number) AS card_key
          FROM forum.forum_cards
          WHERE meta.norm_loyalty_card(programm, number) IS NOT NULL
          GROUP BY 1 HAVING count(DISTINCT profile_id) > 1
        ),
        p AS (
          SELECT meta.norm_loyalty_card(bonus_program, card_number) AS card_key
          FROM pointz.pointz_cards
          WHERE meta.norm_loyalty_card(bonus_program, card_number) IS NOT NULL
          GROUP BY 1 HAVING count(DISTINCT user_id) > 1
        )
        SELECT count(*) FROM (
          SELECT card_key FROM f UNION SELECT card_key FROM p
        ) k
        """
    )
    feat_conf = await conn.fetchval("SELECT count(*) FROM feat.card_conflict")
    if raw_conf != feat_conf:
        fail(f"card_conflict: raw={raw_conf} feat={feat_conf}")
    else:
        fine(f"card_conflict cards={feat_conf} (= сырьё)")

    missing = await conn.fetchval(
        """
        SELECT count(*) FROM feat.person_features f
        WHERE f.card_multi_profile_n > 0
          AND NOT EXISTS (
            SELECT 1 FROM feat.card_conflict c WHERE c.person_id = f.person_id
          )
        """
    )
    if missing:
        fail(f"card_multi>0 без card_conflict: {missing}")
    else:
        fine("card_multi>0 ⇒ есть строки в card_conflict")

    print()
    print("PASS" if ok else "FAILED")
    await conn.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
