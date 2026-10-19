"""
Гипотеза «хвост» (route_tail): B повторяет маршрут A с задержкой,
на не самых массовых маршрутах, несколько раз.

Время бронирования в данных отсутствует → в detail явно пишем «не проверялось».
"""

from __future__ import annotations

from analysis.config import SEVERITY, SHADOW
from analysis.db import cursor

SQL_FIND_PAIRS = """
WITH route_stats AS (
    SELECT from_airport, to_airport, count(*) AS n
    FROM work.flight
    WHERE coalesce(from_airport, '') NOT IN ('', 'REA')
      AND coalesce(to_airport, '') NOT IN ('', 'REA')
    GROUP BY 1, 2
    HAVING count(*) BETWEEN %(min_route)s AND %(max_route)s
),
f AS (
    SELECT fl.passenger_id, fl.flight_id, fl.flight_date,
           fl.flight_number, fl.from_airport, fl.to_airport
    FROM work.flight fl
    JOIN route_stats r
      ON r.from_airport = fl.from_airport
     AND r.to_airport = fl.to_airport
),
pairs AS (
    SELECT
        a.passenger_id AS leader_id,
        b.passenger_id AS follower_id,
        a.from_airport,
        a.to_airport,
        count(*) AS repeats,
        round(avg(b.flight_date - a.flight_date)::numeric, 2) AS avg_delay_days,
        min(a.flight_date) AS first_leader_date,
        max(b.flight_date) AS last_follower_date
    FROM f a
    JOIN f b
      ON a.from_airport = b.from_airport
     AND a.to_airport = b.to_airport
     AND a.passenger_id <> b.passenger_id
     AND (b.flight_date - a.flight_date)
         BETWEEN %(dmin)s AND %(dmax)s
    GROUP BY 1, 2, 3, 4
    HAVING count(*) >= %(min_repeats)s
)
SELECT * FROM pairs
ORDER BY repeats DESC, avg_delay_days
LIMIT %(limit)s;
"""


def run(*, replace: bool = True) -> int:
    sev = SEVERITY["route_tail"]
    with cursor() as cur:
        if replace:
            cur.execute(
                """
                DELETE FROM work.evidence
                WHERE finding_id IN (
                    SELECT finding_id FROM work.finding
                    WHERE finding_type = 'route_tail'
                )
                """
            )
            cur.execute(
                "DELETE FROM work.finding WHERE finding_type = 'route_tail'"
            )

        cur.execute(
            SQL_FIND_PAIRS,
            {
                "min_route": SHADOW["min_route_flights"],
                "max_route": SHADOW["max_route_flights"],
                "dmin": SHADOW["delay_min_days"],
                "dmax": SHADOW["delay_max_days"],
                "min_repeats": SHADOW["min_repeats"],
                "limit": SHADOW["top_pairs"],
            },
        )
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        found = 0

        for row in rows:
            rec = dict(zip(cols, row))
            detail = (
                f"Follower повторяет маршрут {rec['from_airport']}→{rec['to_airport']} "
                f"за лидером {rec['leader_id']}: {rec['repeats']} раз(а), "
                f"средняя задержка {rec['avg_delay_days']} дн. "
                f"(окно {SHADOW['delay_min_days']}–{SHADOW['delay_max_days']} дн.). "
                f"Время бронирования в данных отсутствует — не проверялось."
            )
            cur.execute(
                """
                INSERT INTO work.finding (
                    passenger_id, finding_type, title, detail,
                    period_start, period_end, severity, status
                ) VALUES (
                    %(follower_id)s, 'route_tail',
                    'Совпадение маршрутов во времени (хвост)',
                    %(detail)s, %(period_start)s, %(period_end)s,
                    %(severity)s, 'needs_check'
                )
                RETURNING finding_id
                """,
                {
                    "follower_id": rec["follower_id"],
                    "detail": detail,
                    "period_start": rec["first_leader_date"],
                    "period_end": rec["last_follower_date"],
                    "severity": sev,
                },
            )
            finding_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO work.evidence (finding_id, kind, label) VALUES
                    (%s, 'note', %s),
                    (%s, 'note', %s),
                    (%s, 'note', %s)
                """,
                (
                    finding_id,
                    f"лидер: {rec['leader_id']}",
                    finding_id,
                    f"маршрут: {rec['from_airport']}→{rec['to_airport']}",
                    finding_id,
                    f"повторов={rec['repeats']}, avg_delay_days={rec['avg_delay_days']}",
                ),
            )
            found += 1

    return found
