-- Склейка cardless Forum ↔ Sirena без FF# по уникальным рейсам.
-- 1) материализуем ноги  2) считаем shared  3) unique best с обеих сторон ≥ __MIN_SHARED__

TRUNCATE stage.flight_match;
TRUNCATE stage.cardless_forum_leg;
TRUNCATE stage.cardless_sirena_leg;

INSERT INTO stage.cardless_forum_leg (
  profile_id, flight_date, flight_number, from_airport, to_airport
)
SELECT DISTINCT
  ff.profile_id,
  NULLIF(btrim(ff.flight_date), '')::date,
  upper(btrim(ff.flight_number)),
  upper(btrim(ff.dep_airport)),
  upper(btrim(ff.arr_airport))
FROM forum.forum_flights ff
WHERE nullif(btrim(ff.profile_id), '') IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM forum.forum_cards fc
    WHERE fc.profile_id = ff.profile_id
      AND nullif(btrim(fc.number), '') IS NOT NULL
  )
  AND NULLIF(btrim(ff.flight_date), '') ~ '^\d{4}-\d{2}-\d{2}$'
  AND NULLIF(btrim(ff.flight_number), '') IS NOT NULL
  AND nullif(btrim(ff.dep_airport), '') IS NOT NULL
  AND nullif(btrim(ff.arr_airport), '') IS NOT NULL;

ANALYZE stage.cardless_forum_leg;

INSERT INTO stage.cardless_sirena_leg (
  doc_key, flight_date, flight_number, from_airport, to_airport
)
SELECT DISTINCT
  upper(regexp_replace(btrim(s.traveldoc), '[^0-9A-Za-z]', '', 'g')),
  NULLIF(btrim(s.departdate), '')::date,
  upper(btrim(s.flightcode)),
  upper(btrim(s."from")),
  upper(btrim(s.dest))
FROM skyteam.sirena_records s
WHERE coalesce(btrim(s.traveldoc), '') NOT IN ('', 'N/A')
  AND NOT (coalesce(s.paxadditionalinfo, '') ~ 'FF#[A-Za-z]{2}')
  AND NULLIF(btrim(s.departdate), '') ~ '^\d{4}-\d{2}-\d{2}$'
  AND NULLIF(btrim(s.flightcode), '') IS NOT NULL
  AND nullif(btrim(s."from"), '') IS NOT NULL
  AND nullif(btrim(s.dest), '') IS NOT NULL
  AND length(regexp_replace(btrim(s.traveldoc), '[^0-9A-Za-z]', '', 'g')) > 0;

ANALYZE stage.cardless_sirena_leg;

INSERT INTO stage.flight_match (
  profile_id, doc_key, shared_legs, n_profile_ties, n_doc_ties, assigned, target_person_id
)
WITH shared AS (
  SELECT
    f.profile_id,
    s.doc_key,
    count(*)::int AS shared_legs
  FROM stage.cardless_forum_leg f
  JOIN stage.cardless_sirena_leg s
    ON s.flight_date = f.flight_date
   AND s.flight_number = f.flight_number
   AND s.from_airport = f.from_airport
   AND s.to_airport = f.to_airport
  GROUP BY f.profile_id, s.doc_key
),
profile_best AS (
  SELECT profile_id, max(shared_legs) AS best_shared
  FROM shared
  GROUP BY profile_id
),
doc_best AS (
  SELECT doc_key, max(shared_legs) AS best_shared
  FROM shared
  GROUP BY doc_key
),
profile_ties AS (
  SELECT s.profile_id, s.shared_legs, count(*)::int AS n_ties
  FROM shared s
  JOIN profile_best b
    ON b.profile_id = s.profile_id AND b.best_shared = s.shared_legs
  GROUP BY s.profile_id, s.shared_legs
),
doc_ties AS (
  SELECT s.doc_key, s.shared_legs, count(*)::int AS n_ties
  FROM shared s
  JOIN doc_best b
    ON b.doc_key = s.doc_key AND b.best_shared = s.shared_legs
  GROUP BY s.doc_key, s.shared_legs
)
SELECT
  s.profile_id,
  s.doc_key,
  s.shared_legs,
  coalesce(pt.n_ties, 0),
  coalesce(dt.n_ties, 0),
  (
    s.shared_legs >= __MIN_SHARED__
    AND pb.best_shared = s.shared_legs
    AND db.best_shared = s.shared_legs
    AND coalesce(pt.n_ties, 0) = 1
    AND coalesce(dt.n_ties, 0) = 1
  ) AS assigned,
  CASE
    WHEN s.shared_legs >= __MIN_SHARED__
     AND pb.best_shared = s.shared_legs
     AND db.best_shared = s.shared_legs
     AND coalesce(pt.n_ties, 0) = 1
     AND coalesce(dt.n_ties, 0) = 1
    THEN doc.person_id
    ELSE NULL
  END AS target_person_id
FROM shared s
JOIN profile_best pb ON pb.profile_id = s.profile_id
JOIN doc_best db ON db.doc_key = s.doc_key
LEFT JOIN profile_ties pt
  ON pt.profile_id = s.profile_id AND pt.shared_legs = s.shared_legs
LEFT JOIN doc_ties dt
  ON dt.doc_key = s.doc_key AND dt.shared_legs = s.shared_legs
LEFT JOIN stage.doc_on_card doc ON doc.doc_key = s.doc_key;

ANALYZE stage.flight_match;
