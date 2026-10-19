-- Комментарии схемы work (DBeaver → Description)

COMMENT ON SCHEMA work IS 'Рабочие таблицы для анализа. Используйте только их.';

COMMENT ON TABLE work.passenger IS 'Пассажир = карта лояльности. 1 строка = 1 человек в модели v1.';
COMMENT ON COLUMN work.passenger.passenger_id IS 'Ключ: card:PROGRAM NUMBER, пример card:FB 171388778.';
COMMENT ON COLUMN work.passenger.card_program IS 'Программа: FB, KE, SU, DT…';
COMMENT ON COLUMN work.passenger.card_number IS 'Номер карты (цифры).';
COMMENT ON COLUMN work.passenger.flights_n IS 'Число уникальных перелётов после дедупа.';
COMMENT ON COLUMN work.passenger.first_flight IS 'Дата первого перелёта.';
COMMENT ON COLUMN work.passenger.last_flight IS 'Дата последнего перелёта.';

COMMENT ON TABLE work.passenger_name IS 'ФИО из разных источников (отдельные строки).';
COMMENT ON COLUMN work.passenger_name.passenger_id IS '→ work.passenger';
COMMENT ON COLUMN work.passenger_name.source IS 'forum | pointz';
COMMENT ON COLUMN work.passenger_name.full_name IS 'ФИО как в источнике (транслит может отличаться).';

COMMENT ON TABLE work.flight IS 'Уникальный перелёт (дата+рейс+маршрут).';
COMMENT ON COLUMN work.flight.flight_id IS 'ID → work.evidence.flight_id';
COMMENT ON COLUMN work.flight.passenger_id IS '→ work.passenger';
COMMENT ON COLUMN work.flight.flight_date IS 'Дата вылета.';
COMMENT ON COLUMN work.flight.flight_number IS 'Номер рейса.';
COMMENT ON COLUMN work.flight.from_airport IS 'IATA вылета.';
COMMENT ON COLUMN work.flight.to_airport IS 'IATA прилёта.';

COMMENT ON TABLE work.flight_source IS 'Источники перелёта (вместо списка в одной колонке).';
COMMENT ON COLUMN work.flight_source.flight_id IS '→ work.flight';
COMMENT ON COLUMN work.flight_source.source IS 'skyteam | forum | pointz | sirena';

COMMENT ON TABLE work.finding IS 'Находка по критерию. Не ярлык «шпион», а факт для ручной проверки.';
COMMENT ON COLUMN work.finding.finding_id IS 'ID → work.evidence';
COMMENT ON COLUMN work.finding.passenger_id IS '→ work.passenger';
COMMENT ON COLUMN work.finding.finding_type IS 'high_freq|spike|route_gap|quick_return|flight_conflict|id_conflict|doc_conflict|card_multi_owner|route_tail. Веса: analysis/config.py';
COMMENT ON COLUMN work.finding.title IS 'Краткий заголовок.';
COMMENT ON COLUMN work.finding.detail IS 'Что проверить руками.';
COMMENT ON COLUMN work.finding.period_start IS 'Начало периода / дата 1-го рейса.';
COMMENT ON COLUMN work.finding.period_end IS 'Конец периода / дата 2-го рейса.';
COMMENT ON COLUMN work.finding.severity IS '1=слабо, 2=средне, 3=сильно (из analysis/config.py).';
COMMENT ON COLUMN work.finding.status IS 'needs_check | confirmed | false_alarm';

COMMENT ON TABLE work.evidence IS 'Конкретные строки для проверки находки.';
COMMENT ON COLUMN work.evidence.evidence_id IS 'ID доказательства.';
COMMENT ON COLUMN work.evidence.finding_id IS '→ work.finding';
COMMENT ON COLUMN work.evidence.flight_id IS '→ work.flight (если kind=flight), иначе NULL.';
COMMENT ON COLUMN work.evidence.kind IS 'flight | name | note';
COMMENT ON COLUMN work.evidence.label IS 'Подпись доказательства.';

COMMENT ON VIEW work.v_abc IS 'A/B/C: A ≈ топ 10% score, B средние, C остальные. Детали — work.finding / work.evidence по passenger_id.';
