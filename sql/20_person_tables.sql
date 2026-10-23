-- =============================================================================
-- Витрины в схеме feat (сырьё: forum / skyteam / pointz):
--
--   feat.person_features  — только числа для модели
--   feat.person_evidence  — пояснения и id строк источников (FK 1:1)
--   feat.person           — сущность пользователя (ФИО, ДР, документы, карты)
--   feat.flight           — каталог рейсов (сколько людей, страны, источники)
--   feat.card_conflict    — карта у ≥2 аккаунтов (аномалия)
--
-- Сборка:  python -m analysis.build_person_wide
-- =============================================================================

DROP SCHEMA IF EXISTS work CASCADE;

CREATE SCHEMA IF NOT EXISTS feat;
COMMENT ON SCHEMA feat IS
  'Признаки по людям. Сырьё — forum/skyteam/pointz; промежуточное — stage; сюда — результат.';

DROP TABLE IF EXISTS feat.card_conflict CASCADE;
DROP TABLE IF EXISTS feat.person_evidence CASCADE;
DROP TABLE IF EXISTS feat.person CASCADE;
DROP TABLE IF EXISTS feat.flight CASCADE;
DROP TABLE IF EXISTS feat.person_card CASCADE;
DROP TABLE IF EXISTS feat.person_anchor CASCADE;
DROP TABLE IF EXISTS feat.person_features CASCADE;

-- ---------- 1) Цифры для модели ----------
CREATE TABLE feat.person_features (
  person_id                bigserial PRIMARY KEY,

  -- как собран человек: card | flight_match | forum_profile | sirena_doc
  identity_kind            text NOT NULL DEFAULT 'card',
  -- false = не удалось привязать паспорт (forum без матча к Sirena)
  identity_resolved        boolean NOT NULL DEFAULT true,
  -- сколько уникальных общих рейсов Forum↔Sirena при flight_match (иначе 0)
  match_shared_legs        int NOT NULL DEFAULT 0,

  cards_n                  int NOT NULL DEFAULT 0,
  names_distinct_n         int NOT NULL DEFAULT 0,
  flights_n                int NOT NULL DEFAULT 0,
  flight_span_days         int NOT NULL DEFAULT 0,

  high_freq_windows_n      int NOT NULL DEFAULT 0,
  high_freq_max_flights_30d int NOT NULL DEFAULT 0,
  spike_windows_n          int NOT NULL DEFAULT 0,
  route_gap_n              int NOT NULL DEFAULT 0,
  quick_return_n           int NOT NULL DEFAULT 0,
  flight_conflict_n        int NOT NULL DEFAULT 0,
  name_conflict_n          int NOT NULL DEFAULT 0,
  doc_rf_conflict_n        int NOT NULL DEFAULT 0,
  doc_foreign_conflict_n   int NOT NULL DEFAULT 0,
  doc_other_conflict_n     int NOT NULL DEFAULT 0,
  card_multi_profile_n     int NOT NULL DEFAULT 0,
  route_tail_n             int NOT NULL DEFAULT 0,
  route_tail_rare_n        int NOT NULL DEFAULT 0
);

COMMENT ON TABLE feat.person_features IS
  'Числовая матрица признаков: одна строка = один человек (person_id). Без текстов и списков id — удобно отдавать в ML.';

COMMENT ON COLUMN feat.person_features.person_id IS
  'Суррогатный id человека. Сначала 1..Nc по картам (min card_key), затем cardless. '
  'После DROP+полной пересборки может сдвинуться.';
COMMENT ON COLUMN feat.person_features.identity_kind IS
  'card = склейка по картам; flight_match = forum↔sirena по ≥K рейсам; '
  'forum_profile = только форум без паспорта; sirena_doc = только traveldoc без FF#.';
COMMENT ON COLUMN feat.person_features.identity_resolved IS
  'true если есть карта и/или traveldoc; false — forum без надёжного матча (для статы, пометка «хз»).';
COMMENT ON COLUMN feat.person_features.match_shared_legs IS
  'Число уникальных совпавших рейсов (дата+номер+OD) при склейке flight_match; иначе 0.';
COMMENT ON COLUMN feat.person_features.cards_n IS
  'Сколько карт лояльности склеили в этого человека.';
COMMENT ON COLUMN feat.person_features.names_distinct_n IS
  'Сколько разных написаний ФИО (forum+pointz+sirena). Шумно из‑за транслита — для ML осторожно.';
COMMENT ON COLUMN feat.person_features.flights_n IS
  'Число уникальных перелётов (дата+рейс+маршрут) после дедупа источников.';
COMMENT ON COLUMN feat.person_features.flight_span_days IS
  'Разница в днях между первым и последним перелётом (0 если одного дня / нет дат).';
COMMENT ON COLUMN feat.person_features.high_freq_windows_n IS
  'Число НЕПЕРЕСЕКАЮЩИХСЯ 30-дневных пиков с ≥ HIGH_FREQ_MIN_FLIGHTS_30D рейсами (config).';
COMMENT ON COLUMN feat.person_features.high_freq_max_flights_30d IS
  'Максимум рейсов в любом скользящем окне 30 дней (главный признак частоты для модели).';
COMMENT ON COLUMN feat.person_features.spike_windows_n IS
  'Число непересекающихся окон всплеска: now_30d/prev_30d ≥ SPIKE_MIN_RATIO '
  'при now ≥ SPIKE_MIN_NOW и prev > 0 (иначе недостаточно истории).';
COMMENT ON COLUMN feat.person_features.flight_conflict_n IS
  'Конфликты маршрута между источниками; часто шум forum↔skyteam — не единственный сигнал.';
COMMENT ON COLUMN feat.person_features.route_gap_n IS
  'Сколько раз прилёт ≠ следующий вылет (разрыв маршрута).';
COMMENT ON COLUMN feat.person_features.quick_return_n IS
  'Сколько пар туда-обратно за ≤ N дней.';
COMMENT ON COLUMN feat.person_features.name_conflict_n IS
  'max(0, names_distinct_n - 1) — «лишние» варианты имени (часто транслит).';
COMMENT ON COLUMN feat.person_features.doc_rf_conflict_n IS
  'Лишние паспорта РФ (эвристика: 10 цифр в traveldoc). Finding: ≥2 разных номера.';
COMMENT ON COLUMN feat.person_features.doc_foreign_conflict_n IS
  'Лишние загранпаспорта (эвристика: 9 цифр в traveldoc). Finding: ≥2 разных номера.';
COMMENT ON COLUMN feat.person_features.doc_other_conflict_n IS
  'Лишние traveldoc иного формата (не 9 и не 10 цифр). Finding: ≥2 разных номера.';
COMMENT ON COLUMN feat.person_features.card_multi_profile_n IS
  'ПРИОРИТЕТНЫЙ finding-сигнал (не шум): сумма числа forum-профилей и pointz-user '
  'на конфликтных картах (карта у ≥2 аккаунтов до склейки). Детали — feat.card_conflict. '
  'person_id здесь = кластер по карте, не гарантия «один физический человек».';
COMMENT ON COLUMN feat.person_features.route_tail_n IS
  'Хвост на средних OD (SHADOW_ROUTE_*): пар leader×маршрут с ≥SHADOW_MIN_REPEATS.';
COMMENT ON COLUMN feat.person_features.route_tail_rare_n IS
  'Хвост на редких OD (SHADOW_RARE_ROUTE_*): сильнее как finding — малолюдный маршрут.';

-- сущность пользователя (1:1 с person_features)
CREATE TABLE feat.person (
  person_id            bigint PRIMARY KEY
                       REFERENCES feat.person_features(person_id) ON DELETE CASCADE,
  birth_date           date,
  name_forum           text,
  name_pointz          text,
  name_sirena          text,
  doc_passport_rf      text,
  doc_passport_foreign text,
  cards                text
);
COMMENT ON TABLE feat.person IS
  'Сущность пользователя для отчётов: ДР, ФИО по источникам, паспорт РФ / загран, список карт. '
  'NULL = нет данных. Карты и якоря для сборки остаются в stage.card_person / stage.person_anchor.';
COMMENT ON COLUMN feat.person.birth_date IS
  'Дата рождения из Sirena (мода валидных YYYY-MM-DD; N/A и мусор отбрасываются). '
  'В forum/pointz ДР нет.';
COMMENT ON COLUMN feat.person.doc_passport_rf IS
  'Паспорт РФ: traveldoc с 10 цифрами (если несколько — через « | »).';
COMMENT ON COLUMN feat.person.doc_passport_foreign IS
  'Загран: traveldoc с 9 цифрами (если несколько — через « | »).';
COMMENT ON COLUMN feat.person.cards IS
  'Карты лояльности через « | » (нормализованные, как в stage.card_person).';

-- каталог физических рейсов (для статистики / отчёта)
CREATE TABLE feat.flight (
  flight_date   date NOT NULL,
  flight_number text NOT NULL,
  from_airport  text NOT NULL DEFAULT '',
  to_airport    text NOT NULL DEFAULT '',
  from_country  text,
  to_country    text,
  people_n      int NOT NULL,
  sources       text,
  PRIMARY KEY (flight_date, flight_number, from_airport, to_airport)
);
CREATE INDEX ON feat.flight (people_n DESC);
CREATE INDEX ON feat.flight (from_country, to_country);
COMMENT ON TABLE feat.flight IS
  'Один физический рейс (дата+номер+OD): сколько наших person_id на нём летело, страны, '
  'какие источники его видели (forum/skyteam/pointz/sirena).';
COMMENT ON COLUMN feat.flight.flight_number IS
  'Номер авиарейса из источников (SU1383, DL1280) — не наш суррогатный id. '
  'Одинаковый номер в forum и Sirena значит «тот же коммерческий рейс», не FK между таблицами.';
COMMENT ON COLUMN feat.flight.people_n IS
  'Число distinct person_id в stage.flight_unique на этом ключе рейса.';

-- аномалия: одна карта → несколько аккаунтов (сохраняем, не «проглатываем»)
CREATE TABLE feat.card_conflict (
  card_key           text PRIMARY KEY,
  person_id          bigint NOT NULL
                     REFERENCES feat.person_features(person_id) ON DELETE CASCADE,
  n_forum_profiles   int NOT NULL DEFAULT 0,
  n_pointz_users     int NOT NULL DEFAULT 0,
  forum_profile_ids  text,
  pointz_user_ids    text
);
CREATE INDEX ON feat.card_conflict (person_id);
COMMENT ON TABLE feat.card_conflict IS
  'Конфликт владения картой: card_key привязан к ≥2 forum.profile_id и/или ≥2 pointz.user_id. '
  'Склейка всё равно даёт один person_id (кластер), но все аккаунты здесь сохранены для аудита и finding. '
  'Редкие строки — сильный сигнал, не игнорировать.';

-- ---------- 2) Пояснения / id строк ----------
CREATE TABLE feat.person_evidence (
  person_id              bigint PRIMARY KEY
                         REFERENCES feat.person_features(person_id) ON DELETE CASCADE,

  card_numbers           text,
  names_forum            text,
  names_pointz           text,
  names_sirena           text,
  forum_profile_ids      text,
  pointz_user_ids        text,
  sirena_docs            text,
  first_flight_date      date,
  last_flight_date       date,

  high_freq_from_date              date,
  high_freq_to_date                date,
  spike_from_date                  date,
  spike_to_date                    date,

  high_freq_skyteam_flight_ids     text,
  high_freq_forum_flight_ids       text,
  high_freq_pointz_activity_ids    text,
  high_freq_sirena_record_ids      text,

  spike_skyteam_flight_ids         text,
  spike_forum_flight_ids           text,
  spike_pointz_activity_ids        text,
  spike_sirena_record_ids          text,

  route_gap_skyteam_flight_ids     text,
  route_gap_forum_flight_ids       text,
  route_gap_pointz_activity_ids    text,
  route_gap_sirena_record_ids      text,

  quick_return_skyteam_flight_ids  text,
  quick_return_forum_flight_ids    text,
  quick_return_pointz_activity_ids text,
  quick_return_sirena_record_ids   text,

  flight_conflict_skyteam_flight_ids  text,
  flight_conflict_forum_flight_ids    text,
  flight_conflict_pointz_activity_ids text,
  flight_conflict_sirena_record_ids  text,

  name_conflict_forum_profile_ids  text,
  name_conflict_pointz_user_ids    text,
  name_conflict_sirena_record_ids  text,

  doc_rf_conflict_sirena_record_ids      text,
  doc_foreign_conflict_sirena_record_ids text,
  doc_other_conflict_sirena_record_ids   text,

  card_multi_forum_profile_ids     text,
  card_multi_pointz_user_ids       text,

  route_tail_leader_person_ids     text,
  route_tail_skyteam_flight_ids    text,
  route_tail_forum_flight_ids      text,
  route_tail_pointz_activity_ids   text,
  route_tail_sirena_record_ids     text,

  route_tail_rare_leader_person_ids   text,
  route_tail_rare_skyteam_flight_ids  text,
  route_tail_rare_forum_flight_ids    text,
  route_tail_rare_pointz_activity_ids text,
  route_tail_rare_sirena_record_ids   text
);

COMMENT ON TABLE feat.person_evidence IS
  'Пояснения к person_features: карты, имена, даты и списки суррогатных PK строк источников '
  '(forum.forum_flight_id, skyteam.skyteam_flight_pk, pointz.pointz_activity_pk, skyteam.sirena_record_pk). '
  'NULL в колонке критерия = критерий НЕ сработал (в features там 0) — это норма, не потеря данных. '
  'Только для ручной проверки — в матрицу X модели не класть.';

COMMENT ON COLUMN feat.person_evidence.person_id IS
  'FK → feat.person_features.person_id (1:1).';
COMMENT ON COLUMN feat.person_evidence.card_numbers IS
  'Карты через « | », вид FB 123.';
COMMENT ON COLUMN feat.person_evidence.names_forum IS
  'ФИО из forum_profiles.';
COMMENT ON COLUMN feat.person_evidence.names_pointz IS
  'ФИО из pointz_users.';
COMMENT ON COLUMN feat.person_evidence.names_sirena IS
  'ФИО из sirena_records.paxname.';
COMMENT ON COLUMN feat.person_evidence.forum_profile_ids IS
  'Бизнес-id профилей форума (profile_id).';
COMMENT ON COLUMN feat.person_evidence.pointz_user_ids IS
  'Бизнес-id юзеров Pointz (user_id).';
COMMENT ON COLUMN feat.person_evidence.first_flight_date IS
  'Дата первого перелёта.';
COMMENT ON COLUMN feat.person_evidence.last_flight_date IS
  'Дата последнего перелёта.';
COMMENT ON COLUMN feat.person_evidence.high_freq_from_date IS
  'Начало интервала evidence для high_freq (min window_start пиков).';
COMMENT ON COLUMN feat.person_evidence.high_freq_to_date IS
  'Конец интервала evidence для high_freq (max window_start + окно).';
COMMENT ON COLUMN feat.person_evidence.spike_from_date IS
  'Начало интервала evidence для spike.';
COMMENT ON COLUMN feat.person_evidence.spike_to_date IS
  'Конец интервала evidence для spike.';
COMMENT ON COLUMN feat.person_evidence.high_freq_forum_flight_ids IS
  'Список forum_flights.forum_flight_id через « | ».';
COMMENT ON COLUMN feat.person_evidence.high_freq_skyteam_flight_ids IS
  'Список skyteam_flights.skyteam_flight_pk через « | ».';
COMMENT ON COLUMN feat.person_evidence.high_freq_pointz_activity_ids IS
  'Список pointz_activities.pointz_activity_pk через « | ».';
COMMENT ON COLUMN feat.person_evidence.high_freq_sirena_record_ids IS
  'Список sirena_records.sirena_record_pk через « | ».';
COMMENT ON COLUMN feat.person_evidence.route_tail_leader_person_ids IS
  'person_id людей, чей маршрут повторяли (хвост).';
