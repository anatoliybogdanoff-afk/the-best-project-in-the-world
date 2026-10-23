#!/bin/bash
# Восстановление готовой БД (forum/skyteam/pointz + stage + feat + meta).
# Один раз при первом запуске пустого тома Docker.
set -euo pipefail

echo "=== Restore spy_flights (3–10 мин) ==="
pg_restore \
  -U "${POSTGRES_USER}" \
  -d "${POSTGRES_DB}" \
  --no-owner \
  --no-acl \
  /dump/spy_flights.dump

echo "=== Restore finished ==="
psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 <<'SQL'
SELECT schemaname, count(*) AS tables
FROM pg_tables
WHERE schemaname IN ('forum', 'skyteam', 'pointz', 'stage', 'feat')
GROUP BY 1
ORDER BY 1;

SELECT count(*) AS person_features FROM feat.person_features;
SELECT count(*) AS flight_unique FROM stage.flight_unique;
SQL
