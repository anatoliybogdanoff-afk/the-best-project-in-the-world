-- Высокая частота: непересекающиеся 30-дневные пики.
-- Плейсхолдеры: __THR__ __W_MINUS_1__ __GAP__

TRUNCATE stage.high_freq_windows;
TRUNCATE stage.high_freq_peaks;

CREATE TEMP TABLE _hf_peaks ON COMMIT DROP AS
WITH RECURSIVE per_day AS (
  SELECT person_id, flight_date, count(*) AS n
  FROM stage.flight_unique GROUP BY 1, 2
),
win AS (
  SELECT a.person_id, a.flight_date AS window_start, sum(b.n) AS flights_30d
  FROM per_day a
  JOIN per_day b ON b.person_id = a.person_id
   AND b.flight_date BETWEEN a.flight_date AND a.flight_date + __W_MINUS_1__
  GROUP BY 1, 2
),
hot AS (
  SELECT person_id, window_start, flights_30d
  FROM win WHERE flights_30d >= __THR__
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
),
peaks AS (
  SELECT person_id, window_start, flights_30d FROM chain WHERE is_pick
),
maxes AS (
  SELECT person_id, max(flights_30d)::int AS max_30d
  FROM win
  GROUP BY person_id
  HAVING max(flights_30d) >= __THR__
)
SELECT p.person_id, p.window_start, p.window_start + __W_MINUS_1__ AS window_end,
       p.flights_30d, m.max_30d
FROM peaks p
JOIN maxes m USING (person_id);

INSERT INTO stage.high_freq_peaks (person_id, window_start, window_end, flights_30d)
SELECT person_id, window_start, window_end, flights_30d FROM _hf_peaks;

INSERT INTO stage.high_freq_windows (person_id, windows_n, max_30d, w0, w1)
SELECT person_id,
       count(*)::int,
       max(max_30d),
       min(window_start),
       max(window_end)
FROM _hf_peaks
GROUP BY person_id;
