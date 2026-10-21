-- Пары leader→follower на одном маршруте с задержкой.
-- Плейсхолдеры: __LEGS_TABLE__ __AGG_TABLE__ __IGNORE__ __RMIN__ __RMAX__ __DMIN__ __DMAX__

TRUNCATE __LEGS_TABLE__;
TRUNCATE __AGG_TABLE__;

INSERT INTO __LEGS_TABLE__ (
  follower_id, leader_id, from_airport, to_airport,
  leader_date, follower_date, leader_fn, follower_fn
)
WITH route_stats AS (
  SELECT from_airport, to_airport, count(*) AS n
  FROM stage.flight_unique
  WHERE coalesce(from_airport, '') NOT IN (__IGNORE__)
    AND coalesce(to_airport, '') NOT IN (__IGNORE__)
  GROUP BY 1, 2
  HAVING count(*) BETWEEN __RMIN__ AND __RMAX__
),
f AS (
  SELECT u.person_id, u.flight_date, u.flight_number,
         u.from_airport, u.to_airport
  FROM stage.flight_unique u
  JOIN route_stats r USING (from_airport, to_airport)
)
SELECT
  b.person_id, a.person_id,
  a.from_airport, a.to_airport,
  a.flight_date, b.flight_date,
  a.flight_number, b.flight_number
FROM f a
JOIN f b
  ON a.from_airport = b.from_airport
 AND a.to_airport = b.to_airport
 AND a.person_id <> b.person_id
 AND (b.flight_date - a.flight_date) BETWEEN __DMIN__ AND __DMAX__;
