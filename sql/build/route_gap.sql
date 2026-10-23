-- Разрыв маршрута: прилёт предыдущего ≠ вылет текущего.
--
-- Не считаем гэпом соседние строки с тем же flight_number в тот же день:
-- это конфликт OD в источниках (один рейс, разные from/to), не путешествие.
-- Такие кейсы отражаются в flight_conflict.

TRUNCATE stage.route_gap;

INSERT INTO stage.route_gap
SELECT * FROM stage.route_seq
WHERE prev_to IS NOT NULL
  AND prev_to <> from_airport
  AND NOT (
    flight_date = prev_date
    AND flight_number IS NOT DISTINCT FROM prev_fn
  );
