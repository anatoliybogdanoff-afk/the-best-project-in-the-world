-- =============================================================================
-- МИНИМАЛЬНАЯ схема work (пассажир / рейс / finding / evidence + v_abc)
--
-- Нужны схемы clean/feat (см. sql/archive/05–08). После сборки:
--   python -m analysis.run_analysis   -- веса из analysis/config.py + route_tail/doc_conflict
-- Комментарии: sql/11_work_comments.sql
-- =============================================================================

DROP SCHEMA IF EXISTS work CASCADE;
CREATE SCHEMA work;

-- 1) Пассажир = карта лояльности
CREATE TABLE work.passenger (
  passenger_id  text PRIMARY KEY,  -- card:FB 123
  card_program  text NOT NULL,     -- FB
  card_number   text NOT NULL,     -- 123
  flights_n     int  NOT NULL DEFAULT 0,
  first_flight  date,
  last_flight   date
);

-- 2) Имена отдельно (не список в одной ячейке)
CREATE TABLE work.passenger_name (
  passenger_id text NOT NULL REFERENCES work.passenger(passenger_id),
  source       text NOT NULL,  -- forum | pointz
  full_name    text NOT NULL,
  PRIMARY KEY (passenger_id, source, full_name)
);

-- 3) Перелёт
CREATE TABLE work.flight (
  flight_id     bigserial PRIMARY KEY,
  passenger_id  text NOT NULL REFERENCES work.passenger(passenger_id),
  flight_date   date NOT NULL,
  flight_number text NOT NULL,
  from_airport  text,
  to_airport    text
);
CREATE INDEX ON work.flight (passenger_id, flight_date);
CREATE INDEX ON work.flight (passenger_id, flight_number, flight_date);

-- 4) Из каких источников этот перелёт (вместо CSV-списка в колонке)
CREATE TABLE work.flight_source (
  flight_id bigint NOT NULL REFERENCES work.flight(flight_id) ON DELETE CASCADE,
  source    text NOT NULL,  -- skyteam | forum | pointz | sirena
  PRIMARY KEY (flight_id, source)
);

-- 5) Находка по критерию
CREATE TABLE work.finding (
  finding_id   bigserial PRIMARY KEY,
  passenger_id text NOT NULL REFERENCES work.passenger(passenger_id),
  finding_type text NOT NULL,
  title        text NOT NULL,
  detail       text NOT NULL,
  period_start date,
  period_end   date,
  severity     smallint NOT NULL DEFAULT 1,
  status       text NOT NULL DEFAULT 'needs_check'
);
CREATE INDEX ON work.finding (passenger_id);
CREATE INDEX ON work.finding (finding_type);

-- 6) Доказательство = ссылка на рейс или текст
CREATE TABLE work.evidence (
  evidence_id bigserial PRIMARY KEY,
  finding_id  bigint NOT NULL REFERENCES work.finding(finding_id) ON DELETE CASCADE,
  flight_id   bigint REFERENCES work.flight(flight_id),
  kind        text NOT NULL,   -- flight | name | note
  label       text NOT NULL
);
CREATE INDEX ON work.evidence (finding_id);

-- =============================================================================
BEGIN;

-- пассажиры
INSERT INTO work.passenger (passenger_id, card_program, card_number, flights_n, first_flight, last_flight)
SELECT
  passenger_id,
  loyalty_program,
  loyalty_number,
  unique_flights_all_time,
  first_flight_date,
  last_flight_date
FROM feat.passenger_dossier;

-- имена (по одной строке, без «A | B»)
INSERT INTO work.passenger_name (passenger_id, source, full_name)
SELECT DISTINCT
  pl.passenger_id,
  'forum',
  btrim(coalesce(fp.first_name,'') || ' ' || coalesce(fp.last_name,''))
FROM clean.passenger_links pl
JOIN work.passenger p ON p.passenger_id = pl.passenger_id
JOIN forum_profiles fp ON pl.local_source = 'forum' AND pl.local_id = fp.profile_id
WHERE btrim(coalesce(fp.first_name,'') || ' ' || coalesce(fp.last_name,'')) <> '';

INSERT INTO work.passenger_name (passenger_id, source, full_name)
SELECT DISTINCT
  pl.passenger_id,
  'pointz',
  btrim(coalesce(pu.first_name,'') || ' ' || coalesce(pu.last_name,''))
FROM clean.passenger_links pl
JOIN work.passenger p ON p.passenger_id = pl.passenger_id
JOIN pointz_users pu ON pl.local_source = 'pointz' AND pl.local_id = pu.user_id
WHERE btrim(coalesce(pu.first_name,'') || ' ' || coalesce(pu.last_name,'')) <> ''
ON CONFLICT DO NOTHING;

-- перелёты + map card_key → flight_id через temp
CREATE TEMP TABLE _fe AS
SELECT
  'card:' || card_key AS passenger_id,
  flight_date,
  flight_number,
  from_airport,
  to_airport,
  sources,
  evidence_n,
  row_number() OVER () AS rn
FROM clean.flight_events_unique
WHERE card_key IS NOT NULL AND flight_date IS NOT NULL AND flight_number IS NOT NULL;

INSERT INTO work.flight (passenger_id, flight_date, flight_number, from_airport, to_airport)
SELECT passenger_id, flight_date, flight_number, from_airport, to_airport
FROM _fe
ORDER BY rn;

-- сопоставить вставленные id с источниками (по натуральному ключу)
CREATE TEMP TABLE _fmap AS
SELECT f.flight_id, e.sources
FROM work.flight f
JOIN _fe e
  ON e.passenger_id = f.passenger_id
 AND e.flight_date = f.flight_date
 AND e.flight_number = f.flight_number
 AND e.from_airport IS NOT DISTINCT FROM f.from_airport
 AND e.to_airport IS NOT DISTINCT FROM f.to_airport;

INSERT INTO work.flight_source (flight_id, source)
SELECT DISTINCT flight_id, trim(unnest(string_to_array(sources, ',')))
FROM _fmap
WHERE sources IS NOT NULL AND trim(sources) <> '';

-- ---------- критерий 1: high_freq ----------
CREATE TEMP TABLE _hf AS
SELECT nextval('work.finding_finding_id_seq') AS finding_id,
       passenger_id, period_start, period_end, flights_30d
FROM feat.passenger_features_v1
WHERE flights_30d >= 8;

INSERT INTO work.finding (finding_id, passenger_id, finding_type, title, detail, period_start, period_end, severity)
SELECT finding_id, passenger_id, 'high_freq',
       'Высокая частота перелётов',
       format('Уникальных перелётов за 30 дней: %s (порог ≥ 8). См. evidence — примеры рейсов.', flights_30d),
       period_start, period_end, 2
FROM _hf;

INSERT INTO work.evidence (finding_id, flight_id, kind, label)
SELECT finding_id, flight_id, 'flight', label
FROM (
  SELECT h.finding_id, fl.flight_id,
         format('%s %s %s→%s', fl.flight_date, fl.flight_number, fl.from_airport, fl.to_airport) AS label,
         row_number() OVER (PARTITION BY h.finding_id ORDER BY fl.flight_date, fl.flight_id) AS rn
  FROM _hf h
  JOIN work.flight fl ON fl.passenger_id = h.passenger_id
   AND fl.flight_date BETWEEN h.period_start AND h.period_end
) s WHERE rn <= 20;

-- ---------- критерий 2: spike ----------
CREATE TEMP TABLE _sp AS
SELECT nextval('work.finding_finding_id_seq') AS finding_id,
       passenger_id, period_start, period_end, flights_30d, flights_prev_30d, spike_status, spike_ratio
FROM feat.passenger_features_v1
WHERE spike_status IN ('spike', 'spike_from_zero');

INSERT INTO work.finding (finding_id, passenger_id, finding_type, title, detail, period_start, period_end, severity)
SELECT finding_id, passenger_id, 'spike',
       'Всплеск активности',
       format('%s: сейчас %s, ранее %s, ratio=%s',
              spike_status, flights_30d, flights_prev_30d, coalesce(spike_ratio::text,'NULL')),
       period_start, period_end, 2
FROM _sp;

INSERT INTO work.evidence (finding_id, flight_id, kind, label)
SELECT finding_id, flight_id, 'flight', label FROM (
  SELECT s.finding_id, fl.flight_id,
         format('сейчас: %s %s %s→%s', fl.flight_date, fl.flight_number, fl.from_airport, fl.to_airport) AS label,
         row_number() OVER (PARTITION BY s.finding_id ORDER BY fl.flight_date) rn
  FROM _sp s
  JOIN work.flight fl ON fl.passenger_id = s.passenger_id
   AND fl.flight_date BETWEEN s.period_start AND s.period_end
) x WHERE rn <= 10
UNION ALL
SELECT finding_id, flight_id, 'flight', label FROM (
  SELECT s.finding_id, fl.flight_id,
         format('ранее: %s %s %s→%s', fl.flight_date, fl.flight_number, fl.from_airport, fl.to_airport) AS label,
         row_number() OVER (PARTITION BY s.finding_id ORDER BY fl.flight_date) rn
  FROM _sp s
  JOIN work.flight fl ON fl.passenger_id = s.passenger_id
   AND fl.flight_date BETWEEN (s.period_start - 30) AND (s.period_start - 1)
) y WHERE rn <= 10;

-- ---------- критерий 3: route_gap ----------
CREATE TEMP TABLE _gap AS
WITH o AS (
  SELECT passenger_id, flight_id, flight_date, flight_number, from_airport, to_airport,
         lag(flight_id) OVER (PARTITION BY passenger_id ORDER BY flight_date, flight_number, flight_id) AS prev_id,
         lag(to_airport) OVER (PARTITION BY passenger_id ORDER BY flight_date, flight_number, flight_id) AS prev_to,
         lag(flight_date) OVER (PARTITION BY passenger_id ORDER BY flight_date, flight_number, flight_id) AS prev_date,
         lag(flight_number) OVER (PARTITION BY passenger_id ORDER BY flight_date, flight_number, flight_id) AS prev_fn
  FROM work.flight
  WHERE coalesce(from_airport,'') NOT IN ('','REA')
    AND coalesce(to_airport,'') NOT IN ('','REA')
)
SELECT *, nextval('work.finding_finding_id_seq') AS finding_id
FROM o
WHERE prev_to IS NOT NULL AND prev_to <> from_airport;

INSERT INTO work.finding (finding_id, passenger_id, finding_type, title, detail, period_start, period_end, severity)
SELECT finding_id, passenger_id, 'route_gap',
       'Разрыв маршрута',
       format('Прилёт в %s (%s %s), затем вылет из %s (%s %s)',
              prev_to, prev_date, prev_fn, from_airport, flight_date, flight_number),
       prev_date, flight_date, 2
FROM _gap;

INSERT INTO work.evidence (finding_id, flight_id, kind, label)
SELECT finding_id, prev_id, 'flight', format('1) прилёт в %s', prev_to) FROM _gap
UNION ALL
SELECT finding_id, flight_id, 'flight', format('2) вылет из %s', from_airport) FROM _gap;

-- ---------- критерий 3b: quick_return (туда-обратно ≤ 1 день) — твой критерий ----------
CREATE TEMP TABLE _qr AS
WITH o AS (
  SELECT passenger_id, flight_id, flight_date, flight_number, from_airport, to_airport,
         lag(flight_id) OVER (PARTITION BY passenger_id ORDER BY flight_date, flight_number, flight_id) AS prev_id,
         lag(from_airport) OVER (PARTITION BY passenger_id ORDER BY flight_date, flight_number, flight_id) AS prev_from,
         lag(to_airport) OVER (PARTITION BY passenger_id ORDER BY flight_date, flight_number, flight_id) AS prev_to,
         lag(flight_date) OVER (PARTITION BY passenger_id ORDER BY flight_date, flight_number, flight_id) AS prev_date,
         lag(flight_number) OVER (PARTITION BY passenger_id ORDER BY flight_date, flight_number, flight_id) AS prev_fn
  FROM work.flight
  WHERE coalesce(from_airport,'') NOT IN ('','REA')
    AND coalesce(to_airport,'') NOT IN ('','REA')
)
SELECT *, nextval('work.finding_finding_id_seq') AS finding_id
FROM o
WHERE prev_from IS NOT NULL
  AND from_airport = prev_to
  AND to_airport = prev_from
  AND flight_date - prev_date <= 1;

INSERT INTO work.finding (finding_id, passenger_id, finding_type, title, detail, period_start, period_end, severity)
SELECT finding_id, passenger_id, 'quick_return',
       'Быстрый возврат туда-обратно',
       format('%s→%s (%s %s), обратно %s→%s (%s %s), разница дней=%s. Времени в исходниках часто нет — проверь вручную.',
              prev_from, prev_to, prev_date, prev_fn,
              from_airport, to_airport, flight_date, flight_number,
              (flight_date - prev_date)),
       prev_date, flight_date, 2
FROM _qr;

INSERT INTO work.evidence (finding_id, flight_id, kind, label)
SELECT finding_id, prev_id, 'flight', '1) туда' FROM _qr
UNION ALL
SELECT finding_id, flight_id, 'flight', '2) обратно' FROM _qr;

-- ---------- критерий 4: flight_conflict ----------
CREATE TEMP TABLE _fc AS
SELECT nextval('work.finding_finding_id_seq') AS finding_id,
       'card:' || card_key AS passenger_id,
       flight_date, flight_number, routes, source_sets
FROM clean.flight_conflicts;

INSERT INTO work.finding (finding_id, passenger_id, finding_type, title, detail, period_start, period_end, severity)
SELECT finding_id, passenger_id, 'flight_conflict',
       'Расхождение источников',
       format('Дата %s рейс %s: разные маршруты [%s], источники [%s]',
              flight_date, flight_number, routes, source_sets),
       flight_date, flight_date, 3
FROM _fc;

INSERT INTO work.evidence (finding_id, flight_id, kind, label)
SELECT fc.finding_id, fl.flight_id, 'flight',
       format('%s→%s', fl.from_airport, fl.to_airport)
FROM _fc fc
JOIN work.flight fl
  ON fl.passenger_id = fc.passenger_id
 AND fl.flight_date = fc.flight_date
 AND fl.flight_number = fc.flight_number;

-- ---------- критерий 5: id_conflict ----------
CREATE TEMP TABLE _idc AS
SELECT nextval('work.finding_finding_id_seq') AS finding_id,
       'card:' || card_key AS passenger_id,
       forum_fio, pointz_fio
FROM clean.id_conflicts;

INSERT INTO work.finding (finding_id, passenger_id, finding_type, title, detail, severity)
SELECT finding_id, passenger_id, 'id_conflict',
       'Разные ФИО на одной карте',
       'Сравни имена в evidence (часто транслит). Не ставь шпиона автоматом.',
       1
FROM _idc;

INSERT INTO work.evidence (finding_id, kind, label)
SELECT finding_id, 'name', format('forum: %s', forum_fio) FROM _idc
UNION ALL
SELECT finding_id, 'name', format('pointz: %s', pointz_fio) FROM _idc;

-- ---------- критерий 6: multi owner ----------
CREATE TEMP TABLE _mo AS
SELECT nextval('work.finding_finding_id_seq') AS finding_id,
       'card:' || card_key AS passenger_id,
       forum_profiles_n, profile_ids, pointz_users_n, user_ids
FROM clean.card_owner_conflicts;

INSERT INTO work.finding (finding_id, passenger_id, finding_type, title, detail, severity)
SELECT finding_id, passenger_id, 'card_multi_owner',
       'Карта у нескольких профилей',
       format('forum_profiles=%s; pointz_users=%s — см. evidence',
              forum_profiles_n, pointz_users_n),
       3
FROM _mo;

INSERT INTO work.evidence (finding_id, kind, label)
SELECT finding_id, 'note', format('forum profile_ids: %s', coalesce(profile_ids,'-')) FROM _mo
UNION ALL
SELECT finding_id, 'note', format('pointz user_ids: %s', coalesce(user_ids,'-')) FROM _mo;

COMMIT;

-- Единственная витрина: A / B / C по сумме severity
CREATE OR REPLACE VIEW work.v_abc AS
WITH scored AS (
  SELECT
    p.passenger_id,
    p.card_program,
    p.card_number,
    p.flights_n,
    p.first_flight,
    p.last_flight,
    count(f.finding_id) AS findings_n,
    coalesce(sum(f.severity), 0)::bigint AS suspicion_score
  FROM work.passenger p
  LEFT JOIN work.finding f ON f.passenger_id = p.passenger_id
  GROUP BY p.passenger_id, p.card_program, p.card_number,
           p.flights_n, p.first_flight, p.last_flight
),
bounds AS (
  SELECT
    percentile_cont(0.90) WITHIN GROUP (ORDER BY suspicion_score::float8) AS p90,
    percentile_cont(0.60) WITHIN GROUP (ORDER BY suspicion_score::float8) AS p60
  FROM scored
  WHERE findings_n > 0
)
SELECT
  s.*,
  CASE
    WHEN s.findings_n = 0 THEN 'C'
    WHEN s.suspicion_score::float8 >= b.p90 THEN 'A'
    WHEN s.suspicion_score::float8 >= b.p60 THEN 'B'
    ELSE 'C'
  END AS risk_tier,
  CASE
    WHEN s.findings_n = 0 THEN 'Нет находок — низкий приоритет'
    WHEN s.suspicion_score::float8 >= b.p90 THEN 'Топ ~10% score — проверить первыми'
    WHEN s.suspicion_score::float8 >= b.p60 THEN 'Средний приоритет'
    ELSE 'Слабые находки — низкий приоритет'
  END AS tier_reason
FROM scored s
CROSS JOIN bounds b;

ANALYZE work.passenger;
ANALYZE work.flight;
ANALYZE work.finding;
ANALYZE work.evidence;
