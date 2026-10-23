#!/usr/bin/env bash
# Сверка row counts с dump/manifest_row_counts.tsv (после docker restore).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="${ROOT}/dump/manifest_row_counts.tsv"
HOST="${SPY_PG_HOST:-127.0.0.1}"
PORT="${SPY_PG_PORT:-5434}"
export PGPASSWORD="${SPY_PG_PASSWORD:-spy}"

if [[ ! -f "$MANIFEST" ]]; then
  echo "MISSING $MANIFEST"
  exit 1
fi

psql -h "$HOST" -p "$PORT" -U spy -d spy_flights -v ON_ERROR_STOP=1 -tAc \
  "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   WHERE n.nspname='meta' AND p.proname='norm_loyalty_card'" | grep -q 1 \
  || { echo "FAIL meta.norm_loyalty_card"; exit 1; }

fail=0
while IFS='|' read -r table exp; do
  [[ -z "$table" ]] && continue
  act=$(psql -h "$HOST" -p "$PORT" -U spy -d spy_flights -tAc "SELECT count(*) FROM ${table}")
  if [[ "$act" != "$exp" ]]; then
    echo "MISMATCH $table expected=$exp got=$act"
    fail=1
  fi
done < "$MANIFEST"

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

n=$(wc -l < "$MANIFEST")
echo "OK  $n tables match manifest (feat.person_features=$(
  psql -h "$HOST" -p "$PORT" -U spy -d spy_flights -tAc 'SELECT count(*) FROM feat.person_features'
))"
