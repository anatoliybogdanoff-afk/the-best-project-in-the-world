-- Плейсхолдер: __QD__ — макс. дней туда-обратно.
--
-- Берём соседние рейсы в route_seq: текущий = разворот предыдущего (to↔from),
-- задержка ≤ __QD__ дней.
--
-- Исключаем пары «тот же flight_number в тот же день»: в дампе это почти всегда
-- один рейс с перепутанным from/to в разных источниках (forum↔skyteam), а не
-- реальный туда-обратно. Такие кейсы живут в flight_conflict.

TRUNCATE stage.quick_return;

INSERT INTO stage.quick_return
SELECT * FROM stage.route_seq
WHERE prev_from IS NOT NULL
  AND from_airport = prev_to AND to_airport = prev_from
  AND flight_date - prev_date <= __QD__
  AND NOT (
    flight_date = prev_date
    AND flight_number IS NOT DISTINCT FROM prev_fn
  );
