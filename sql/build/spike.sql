-- Всплеск относительно предыдущих 30 дней.
-- Плейсхолдеры: __MIN_NOW__ __RATIO__ __W__ __W_MINUS_1__ __GAP__

TRUNCATE stage.spike_windows;
TRUNCATE stage.spike_peaks;

CREATE TEMP TABLE _spike_peaks ON COMMIT DROP AS
WITH RECURSIVE per_day AS (
  SELECT person_id, flight_date, count(*)::float AS n
  FROM stage.flight_unique GROUP BY 1, 2
),
win AS (
  SELECT a.person_id, a.flight_date AS window_start,
    sum(b.n) FILTER (
      WHERE b.flight_date BETWEEN a.flight_date AND a.flight_date + __W_MINUS_1__
    ) AS now_n,
    sum(b.n) FILTER (
      WHERE b.flight_date BETWEEN a.flight_date - __W__ AND a.flight_date - 1
    ) AS prev_n
  FROM per_day a
  JOIN per_day b ON b.person_id = a.person_id
   AND b.flight_date BETWEEN a.flight_date - __W__ AND a.flight_date + __W_MINUS_1__
  GROUP BY 1, 2
),
hot AS (
  SELECT person_id, window_start, now_n AS flights_30d
  FROM win
  WHERE now_n >= __MIN_NOW__
    AND (
      (coalesce(prev_n, 0) = 0 AND now_n >= __MIN_NOW__)
      OR (prev_n > 0 AND now_n / prev_n >= __RATIO__)
    )
),
ordered AS (
  SELECT person_id, window_start, flights_30d,
         row_number() OVER (PARTITION BY person_id ORDER BY window_start) AS rn
  FROM hot
),
chain AS (
  SELECT person_id, window_start, flights_30d, rn,
         window_start AS cluster_start, TRUE AS is_pick
  FROM ordered WHERE rn = 1
  UNION ALL
  SELECT o.person_id, o.window_start, o.flights_30d, o.rn,
         CASE WHEN o.window_start >= c.cluster_start + __GAP__
              THEN o.window_start ELSE c.cluster_start END,
         (o.window_start >= c.cluster_start + __GAP__)
  FROM chain c
  JOIN ordered o ON o.person_id = c.person_id AND o.rn = c.rn + 1
)
SELECT person_id, window_start, window_start + __W_MINUS_1__ AS window_end, flights_30d
FROM chain WHERE is_pick;

INSERT INTO stage.spike_peaks (person_id, window_start, window_end, flights_30d)
SELECT person_id, window_start, window_end, flights_30d FROM _spike_peaks;

INSERT INTO stage.spike_windows (person_id, windows_n, w0, w1)
SELECT person_id,
       count(*)::int,
       min(window_start),
       max(window_end)
FROM _spike_peaks
GROUP BY person_id;
