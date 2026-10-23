-- Агрегат хвоста + evidence только по qualifying legs.
-- Плейсхолдеры: __LEGS_TABLE__ __AGG_TABLE__ __FEAT_COL__ __EVID_PREFIX__ __REP__

INSERT INTO __AGG_TABLE__ (person_id, n, leaders)
WITH pairs AS (
  SELECT follower_id, leader_id, from_airport, to_airport
  FROM __LEGS_TABLE__
  GROUP BY 1, 2, 3, 4
  HAVING count(*) >= __REP__
),
cnt AS (
  SELECT follower_id, count(*)::int AS n FROM pairs GROUP BY 1
),
leads AS (
  SELECT follower_id,
         string_agg(leader_id::text, ' | ' ORDER BY leader_id) AS leaders
  FROM (SELECT DISTINCT follower_id, leader_id FROM pairs) d
  GROUP BY follower_id
)
SELECT c.follower_id, c.n, l.leaders
FROM cnt c JOIN leads l USING (follower_id);

UPDATE feat.person_features f SET __FEAT_COL__ = t.n
FROM __AGG_TABLE__ t WHERE f.person_id = t.person_id;

UPDATE feat.person_evidence e SET
  __EVID_PREFIX___leader_person_ids = t.leaders,
  __EVID_PREFIX___skyteam_flight_ids = x.sky,
  __EVID_PREFIX___forum_flight_ids = x.frm,
  __EVID_PREFIX___pointz_activity_ids = x.ptz,
  __EVID_PREFIX___sirena_record_ids = x.sir
FROM __AGG_TABLE__ t
LEFT JOIN (
  WITH ok AS (
    SELECT follower_id, leader_id, from_airport, to_airport
    FROM __LEGS_TABLE__
    GROUP BY 1, 2, 3, 4 HAVING count(*) >= __REP__
  ),
  hit AS (
    SELECT DISTINCT leg.follower_id AS person_id, p.src, p.src_id
    FROM __LEGS_TABLE__ leg
    JOIN ok USING (follower_id, leader_id, from_airport, to_airport)
    JOIN stage.flight_event p
      ON p.person_id = leg.follower_id
     AND p.flight_date = leg.follower_date
     AND p.flight_number = leg.follower_fn
  )
  SELECT person_id,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint)
      FILTER (WHERE src = 'skyteam') AS sky,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint)
      FILTER (WHERE src = 'forum') AS frm,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint)
      FILTER (WHERE src = 'pointz') AS ptz,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint)
      FILTER (WHERE src = 'sirena') AS sir
  FROM hit
  GROUP BY person_id
) x ON x.person_id = t.person_id
WHERE e.person_id = t.person_id;
