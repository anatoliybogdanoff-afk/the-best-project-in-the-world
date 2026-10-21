-- =============================================================================
-- Схема stage — промежуточные таблицы сборки (не TEMP: их можно смотреть в DBeaver).
-- Пересоздаются при каждом python -m analysis.build_person_wide.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS stage;
COMMENT ON SCHEMA stage IS
  'Промежуточные таблицы сборки person_features/evidence. Можно открывать и проверять после прогона.';

DROP TABLE IF EXISTS stage.route_tail_leg CASCADE;
DROP TABLE IF EXISTS stage.route_tail CASCADE;
DROP TABLE IF EXISTS stage.route_tail_leg_rare CASCADE;
DROP TABLE IF EXISTS stage.route_tail_rare CASCADE;
DROP TABLE IF EXISTS stage.card_multi CASCADE;
DROP TABLE IF EXISTS stage.doc_conflict CASCADE;
DROP TABLE IF EXISTS stage.flight_conflict CASCADE;
DROP TABLE IF EXISTS stage.quick_return CASCADE;
DROP TABLE IF EXISTS stage.route_gap CASCADE;
DROP TABLE IF EXISTS stage.route_seq CASCADE;
DROP TABLE IF EXISTS stage.spike_peaks CASCADE;
DROP TABLE IF EXISTS stage.spike_windows CASCADE;
DROP TABLE IF EXISTS stage.high_freq_peaks CASCADE;
DROP TABLE IF EXISTS stage.high_freq_windows CASCADE;
DROP TABLE IF EXISTS stage.flight_unique CASCADE;
DROP TABLE IF EXISTS stage.flight_event CASCADE;
DROP TABLE IF EXISTS stage.card_person CASCADE;

-- карта → человек
CREATE TABLE stage.card_person (
  card_key   text PRIMARY KEY,
  person_id  bigint NOT NULL
);
CREATE INDEX ON stage.card_person (person_id);
COMMENT ON TABLE stage.card_person IS
  'Каждая карта лояльности → person_id. Строится при склейке людей.';

-- все упоминания рейсов с источником (для evidence)
CREATE TABLE stage.flight_event (
  person_id     bigint NOT NULL,
  flight_date   date NOT NULL,
  flight_number text NOT NULL,
  from_airport  text,
  to_airport    text,
  src           text NOT NULL,
  src_id        text NOT NULL
);
CREATE INDEX ON stage.flight_event (person_id, flight_date);
CREATE INDEX ON stage.flight_event (person_id, from_airport, to_airport, flight_date);
COMMENT ON TABLE stage.flight_event IS
  'Все перелёты со всех источников. Один физический рейс может быть несколько раз (разный src/src_id).';

-- уникальные перелёты (для счётчиков и маршрутов)
CREATE TABLE stage.flight_unique (
  person_id     bigint NOT NULL,
  flight_date   date NOT NULL,
  flight_number text NOT NULL,
  from_airport  text,
  to_airport    text
);
CREATE INDEX ON stage.flight_unique (person_id, flight_date, flight_number);
COMMENT ON TABLE stage.flight_unique IS
  'Дедуп stage.flight_event: одна строка на person+дата+рейс+маршрут.';

CREATE TABLE stage.high_freq_windows (
  person_id  bigint PRIMARY KEY,
  windows_n  int NOT NULL,
  max_30d    int NOT NULL,
  w0         date,
  w1         date
);

-- Конкретные пики (evidence берёт id только отсюда, не из envelope w0..w1)
CREATE TABLE stage.high_freq_peaks (
  person_id     bigint NOT NULL,
  window_start  date NOT NULL,
  window_end    date NOT NULL,
  flights_30d   numeric NOT NULL
);
CREATE INDEX ON stage.high_freq_peaks (person_id);

CREATE TABLE stage.spike_windows (
  person_id  bigint PRIMARY KEY,
  windows_n  int NOT NULL,
  w0         date,
  w1         date
);

CREATE TABLE stage.spike_peaks (
  person_id     bigint NOT NULL,
  window_start  date NOT NULL,
  window_end    date NOT NULL,
  flights_30d   numeric NOT NULL
);
CREATE INDEX ON stage.spike_peaks (person_id);

CREATE TABLE stage.route_seq (
  person_id     bigint,
  flight_date   date,
  flight_number text,
  from_airport  text,
  to_airport    text,
  prev_date     date,
  prev_fn       text,
  prev_from     text,
  prev_to       text
);

CREATE TABLE stage.route_gap (
  person_id     bigint,
  flight_date   date,
  flight_number text,
  from_airport  text,
  to_airport    text,
  prev_date     date,
  prev_fn       text,
  prev_from     text,
  prev_to       text
);

CREATE TABLE stage.quick_return (
  person_id     bigint,
  flight_date   date,
  flight_number text,
  from_airport  text,
  to_airport    text,
  prev_date     date,
  prev_fn       text,
  prev_from     text,
  prev_to       text
);

CREATE TABLE stage.flight_conflict (
  person_id bigint PRIMARY KEY,
  n         int NOT NULL,
  sky       text,
  frm       text,
  ptz       text,
  sir       text
);

CREATE TABLE stage.doc_conflict (
  person_id     bigint PRIMARY KEY,
  n_docs        int NOT NULL,
  docs          text,
  ids           text,
  n_rf          int NOT NULL DEFAULT 0,
  rf_docs       text,
  rf_ids        text,
  n_foreign     int NOT NULL DEFAULT 0,
  foreign_docs  text,
  foreign_ids   text,
  n_other       int NOT NULL DEFAULT 0,
  other_docs    text,
  other_ids     text
);

CREATE TABLE stage.card_multi (
  person_id  bigint PRIMARY KEY,
  n          int NOT NULL,
  forum_ids  text,
  pointz_ids text
);

CREATE TABLE stage.route_tail (
  person_id bigint PRIMARY KEY,
  n         int NOT NULL,
  leaders   text
);

-- Конкретные ноги «хвоста» (для честного evidence)
CREATE TABLE stage.route_tail_leg (
  follower_id    bigint NOT NULL,
  leader_id      bigint NOT NULL,
  from_airport   text NOT NULL,
  to_airport     text NOT NULL,
  leader_date    date NOT NULL,
  follower_date  date NOT NULL,
  leader_fn      text,
  follower_fn    text
);
CREATE INDEX ON stage.route_tail_leg (follower_id);
COMMENT ON TABLE stage.route_tail_leg IS
  'Пары рейсов leader→follower на одном маршруте с задержкой; отсюда собираем id в evidence.';

-- То же для редких маршрутов (отдельные пороги config SHADOW_RARE_*)
CREATE TABLE stage.route_tail_rare (
  person_id bigint PRIMARY KEY,
  n         int NOT NULL,
  leaders   text
);
CREATE TABLE stage.route_tail_leg_rare (
  follower_id    bigint NOT NULL,
  leader_id      bigint NOT NULL,
  from_airport   text NOT NULL,
  to_airport     text NOT NULL,
  leader_date    date NOT NULL,
  follower_date  date NOT NULL,
  leader_fn      text,
  follower_fn    text
);
CREATE INDEX ON stage.route_tail_leg_rare (follower_id);
COMMENT ON TABLE stage.route_tail_leg_rare IS
  'Ноги хвоста только на редких OD (SHADOW_RARE_ROUTE_*).';
