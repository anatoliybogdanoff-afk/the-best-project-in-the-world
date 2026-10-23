-- Последовательность рейсов человека (для route_gap / quick_return).
-- Плейсхолдер: __IGNORE__ — список вида '','REA' (сравниваем в UPPER).
--
-- 1) Аэропорты нормализуем в UPPER (в сырье много нижнего регистра).
-- 2) Игнор пустых / REA — без учёта регистра.
-- 3) Если в один день один flight_number записан в двух зеркальных OD
--    (forum↔skyteam), оставляем только одну ногу (лексикографически меньший
--    from/to) — иначе цепочка «ломается» ложным разворотом.

TRUNCATE stage.route_seq;

INSERT INTO stage.route_seq
WITH base AS (
  SELECT
    person_id,
    flight_date,
    flight_number,
    upper(from_airport) AS from_airport,
    upper(to_airport) AS to_airport
  FROM stage.flight_unique
  WHERE coalesce(upper(from_airport), '') NOT IN (__IGNORE__)
    AND coalesce(upper(to_airport), '') NOT IN (__IGNORE__)
),
dedup AS (
  SELECT b.*
  FROM base b
  WHERE NOT EXISTS (
    SELECT 1
    FROM base o
    WHERE o.person_id = b.person_id
      AND o.flight_date = b.flight_date
      AND o.flight_number IS NOT DISTINCT FROM b.flight_number
      AND o.from_airport = b.to_airport
      AND o.to_airport = b.from_airport
      AND (o.from_airport, o.to_airport) < (b.from_airport, b.to_airport)
  )
)
SELECT
  person_id, flight_date, flight_number, from_airport, to_airport,
  lag(flight_date) OVER w,
  lag(flight_number) OVER w,
  lag(from_airport) OVER w,
  lag(to_airport) OVER w
FROM dedup
WINDOW w AS (
  PARTITION BY person_id
  ORDER BY flight_date, flight_number, from_airport, to_airport
);
