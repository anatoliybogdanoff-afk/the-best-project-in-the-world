-- Сырые данные по 3 схемам источников (не свалены в public).
--
--   forum   — FrequentFlyer Forum
--   skyteam — SkyTeam Exchange + timetable / sirena / boarding
--   pointz  — Pointz Aggregator
--
-- Имена таблиц те же (forum_profiles, …), меняется только schema.
-- Все поля TEXT, чтобы не потерять нули/пробелы/N/A.

CREATE SCHEMA IF NOT EXISTS meta;
CREATE SCHEMA IF NOT EXISTS forum;
CREATE SCHEMA IF NOT EXISTS skyteam;
CREATE SCHEMA IF NOT EXISTS pointz;

COMMENT ON SCHEMA forum IS 'FrequentFlyer Forum: профили, карты, рейсы, документы.';
COMMENT ON SCHEMA skyteam IS 'SkyTeam Exchange + timetable, sirena, boarding (авиационные выгрузки).';
COMMENT ON SCHEMA pointz IS 'Pointz Aggregator: юзеры, карты, активности, ошибки.';

CREATE TABLE IF NOT EXISTS meta.load_manifest (
    table_name    text PRIMARY KEY,
    expected_rows bigint NOT NULL,
    loaded_rows   bigint,
    checked_at    timestamptz
);

-- ========== forum ==========
CREATE TABLE forum.forum_profiles (
    profile_id  text,
    first_name  text,
    last_name   text,
    sex         text
);

CREATE TABLE forum.forum_documents (
    profile_id       text,
    document_type    text,
    document_number  text
);

CREATE TABLE forum.forum_cards (
    profile_id text,
    number     text,
    status     text,
    programm   text
);

CREATE TABLE forum.forum_flights (
    profile_id    text,
    flight_date   text,
    flight_number text,
    codeshare     text,
    arr_city      text,
    arr_airport   text,
    arr_country   text,
    dep_city      text,
    dep_airport   text,
    dep_country   text
);

-- ========== skyteam (+ связанные авиавыгрузки) ==========
CREATE TABLE skyteam.skyteam_flights (
    flight_id     text,
    date          text,
    flight_number text,
    from_airport  text,
    to_airport    text,
    status        text
);

CREATE TABLE skyteam.skyteam_flight_cards (
    flight_id   text,
    card_number text,
    class       text,
    fare        text
);

CREATE TABLE skyteam.timetable_records (
  "origin_airport" text,
  "destination_airport" text,
  "origin_label" text,
  "destination_label" text,
  "validity_start_raw" text,
  "validity_end_raw" text,
  "validity_start" text,
  "validity_end" text,
  "days_raw" text,
  "days_sunday_1" text,
  "departure_local" text,
  "arrival_local" text,
  "arrival_day_offset" text,
  "flight_number_raw" text,
  "flight_number" text,
  "codeshare_marker" text,
  "aircraft" text,
  "travel_time_raw" text,
  "operator" text,
  "schedule_id" text,
  "source_file" text,
  "source_page" text,
  "source_column" text,
  "source_line" text,
  "raw_line" text
);

CREATE TABLE skyteam.sirena_records (
  "paxname" text,
  "paxbirthdate" text,
  "departdate" text,
  "departtime" text,
  "arrivaldate" text,
  "arrivaltime" text,
  "flightcode" text,
  "sh" text,
  "from" text,
  "dest" text,
  "code" text,
  "e_ticket" text,
  "traveldoc" text,
  "seat" text,
  "meal" text,
  "trvcls" text,
  "fare" text,
  "baggage" text,
  "paxadditionalinfo" text,
  "agentinfo" text,
  "record_id" text,
  "source_file" text,
  "source_line" text,
  "quality_flags" text,
  "raw_line" text
);

CREATE TABLE skyteam.boarding_passes (
    document_title      text,
    sequence_number     text,
    title               text,
    passenger_name      text,
    class_code          text,
    flight_number       text,
    origin_city         text,
    destination_city    text,
    gate                text,
    origin_airport      text,
    destination_airport text,
    flight_date         text,
    flight_time         text,
    operator_note       text,
    boarding_note       text,
    seat                text,
    booking_code        text,
    ticket_number       text,
    source_file         text,
    source_sheet        text,
    file_date           text,
    parse_warnings      text,
    raw_cells_json      text,
    raw_types_json      text
);

CREATE TABLE skyteam.boarding_data (
  "passengerfirstname" text,
  "passengersecondname" text,
  "passengerlastname" text,
  "passengersex" text,
  "passengerbirthdate" text,
  "passengerdocument" text,
  "bookingcode" text,
  "ticketnumber" text,
  "baggage" text,
  "flightdate" text,
  "flighttime" text,
  "flightnumber" text,
  "codeshare" text,
  "destination" text
);

-- ========== pointz ==========
CREATE TABLE pointz.pointz_users (
    user_id    text,
    uid        text,
    first_name text,
    last_name  text
);

CREATE TABLE pointz.pointz_cards (
    card_id        text,
    user_id        text,
    uid            text,
    card_number    text,
    bonus_program  text,
    cards_type     text
);

CREATE TABLE pointz.pointz_activities (
    activity_id     text,
    card_id         text,
    card_number     text,
    uid             text,
    activity_type   text,
    activities_type text,
    code            text,
    date            text,
    departure       text,
    arrival         text,
    fare            text,
    other_fields    text
);

CREATE TABLE pointz.pointz_errors (
    severity    text,
    error_type  text,
    user_id     text,
    uid         text,
    full_name   text,
    card_id     text,
    card_number text,
    activity_id text,
    details     text
);
