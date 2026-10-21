#!/bin/bash
# Загрузка staging CSV в схемы источников (первый init тома Docker).
set -euo pipefail

STAGING="${STAGING_DIR:-/staging}"
echo "=== Loading CSV from ${STAGING} → forum / skyteam / pointz ==="

run_copy() {
  local table="$1"
  local file="$2"
  local rows
  echo "→ ${table} ← ${file}"
  psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" \
    -c "\\copy ${table} FROM '${STAGING}/${file}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')"
  rows=$(psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" \
    -tAc "SELECT count(*) FROM ${table}")
  echo "   rows in DB: ${rows}"
}

run_copy forum.forum_profiles        forum_profiles.csv
run_copy forum.forum_documents       forum_documents.csv
run_copy forum.forum_cards           forum_cards.csv
run_copy forum.forum_flights         forum_flights.csv

run_copy skyteam.skyteam_flights       skyteam_flights.csv
run_copy skyteam.skyteam_flight_cards  skyteam_flight_cards.csv
run_copy skyteam.timetable_records     timetable_records.csv
run_copy skyteam.sirena_records        sirena_records.csv
run_copy skyteam.boarding_passes       boarding_passes.csv
run_copy skyteam.boarding_data         boarding_data.csv

run_copy pointz.pointz_users        pointz_users.csv
run_copy pointz.pointz_cards        pointz_cards.csv
run_copy pointz.pointz_activities   pointz_activities.csv
run_copy pointz.pointz_errors       pointz_errors.csv

echo "=== Load finished ==="
