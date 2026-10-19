#!/bin/bash
# Загрузка staging CSV в Postgres (вызывается при первой инициализации тома).
set -euo pipefail

STAGING="${STAGING_DIR:-/staging}"
echo "=== Loading CSV from ${STAGING} ==="

run_copy() {
  local table="$1"
  local file="$2"
  local rows
  echo "→ ${table} ← ${file}"
  psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" \
    -c "\\copy ${table} FROM '${STAGING}/${file}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')"
  rows=$(psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" -tAc "SELECT count(*) FROM ${table}")
  echo "   rows in DB: ${rows}"
}

run_copy forum_profiles        forum_profiles.csv
run_copy forum_documents       forum_documents.csv
run_copy forum_cards           forum_cards.csv
run_copy forum_flights         forum_flights.csv
run_copy skyteam_flights       skyteam_flights.csv
run_copy skyteam_flight_cards  skyteam_flight_cards.csv
run_copy pointz_users          pointz_users.csv
run_copy pointz_cards          pointz_cards.csv
run_copy pointz_activities     pointz_activities.csv
run_copy pointz_errors         pointz_errors.csv
run_copy boarding_passes       boarding_passes.csv
run_copy boarding_data         boarding_data.csv
run_copy sirena_records        sirena_records.csv
run_copy timetable_records     timetable_records.csv

echo "=== Load finished ==="
