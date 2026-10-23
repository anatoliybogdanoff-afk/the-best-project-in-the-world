Catch the Spies — готовая PostgreSQL в Docker
==============================================

Содержимое архива:
  docker-compose.yml   — Postgres 17, порт 5434
  .env                 — SPY_PG_PORT=5434
  dump/spy_flights.dump — полная БД (~227 MB)
  dump/manifest_row_counts.tsv — эталон строк (35 таблиц)
  sql/01_restore.sh    — restore при первом запуске
  scripts/verify_docker_db.sh — проверка после поднятия

Запуск (Linux/macOS/Windows + Docker Desktop):
  docker compose up -d
  docker compose logs db   # ждём "Restore finished"

Проверка:
  bash scripts/verify_docker_db.sh

DBeaver: localhost:5434, spy / spy, spy_flights

Схемы:
  forum, skyteam, pointz — сырьё
  stage — flight_unique, route_tail_*, …
  feat — person_features, person_evidence, person_card, card_conflict
  meta — norm_loyalty_card (функция)

Подробно для Windows: КАК_ЗАПУСТИТЬ_НА_WINDOWS.txt
