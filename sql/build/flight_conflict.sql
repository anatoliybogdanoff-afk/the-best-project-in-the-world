TRUNCATE stage.flight_conflict;

INSERT INTO stage.flight_conflict (person_id, n, sky, frm, ptz, sir)
WITH routes AS (
  SELECT person_id, flight_date, flight_number,
         from_airport || '→' || to_airport AS route, src, src_id
  FROM stage.flight_event
  WHERE from_airport IS NOT NULL AND to_airport IS NOT NULL
),
clash AS (
  SELECT person_id, flight_date, flight_number
  FROM routes GROUP BY 1, 2, 3 HAVING count(DISTINCT route) > 1
),
tagged AS (
  SELECT DISTINCT c.person_id, r.src, r.src_id
  FROM clash c
  JOIN routes r USING (person_id, flight_date, flight_number)
),
counts AS (
  SELECT person_id, count(*)::int AS n FROM clash GROUP BY person_id
)
SELECT
  c.person_id,
  c.n,
  string_agg(t.src_id, ' | ' ORDER BY t.src_id::bigint)
    FILTER (WHERE t.src = 'skyteam'),
  string_agg(t.src_id, ' | ' ORDER BY t.src_id::bigint)
    FILTER (WHERE t.src = 'forum'),
  string_agg(t.src_id, ' | ' ORDER BY t.src_id::bigint)
    FILTER (WHERE t.src = 'pointz'),
  string_agg(t.src_id, ' | ' ORDER BY t.src_id::bigint)
    FILTER (WHERE t.src = 'sirena')
FROM counts c
LEFT JOIN tagged t ON t.person_id = c.person_id
GROUP BY c.person_id, c.n;
