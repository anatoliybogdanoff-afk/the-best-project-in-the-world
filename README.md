<<<<<<< HEAD
# the-best-project-in-the-world
You won’t see anything worse than this.
=======
# Catch the Spies — DATA (Маша Валова)

PostgreSQL (`work`) + Python-анализ гипотез. Большие CSV/`staging` в Git не кладём.

**Для команды (Windows):** готовый дамп + Docker — архив  
`Загрузки/spy_db_ready.zip` (инструкция внутри: `КАК_ЗАПУСТИТЬ_НА_WINDOWS.txt`).  
Там уже `public` + `work` + `v_abc`, без перегрузки CSV.

## Быстрый старт (эта машина, уже поднятый контейнер)

```bash
docker compose up -d          # порт в .env, обычно 5434
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m analysis.run_analysis   # веса + route_tail + doc_conflict
```

DBeaver: `localhost:5434`, БД `spy_flights`, user/password `spy`/`spy`.

## Где смотреть

| Что | Куда |
|-----|------|
| Кандидаты A/B/C | `work.v_abc` |
| Находки | `work.finding` (`finding_type`, `severity`, `detail`) |
| Доказательства | `work.evidence` → `work.flight` |
| Источник рейса | `work.flight_source` |
| Веса критериев | `analysis/config.py` → `SEVERITY` |
| SQL-сводка | `sql/13_all_hypotheses.sql` |
| Word для команды | `reports/DATA_report_minimal.docx` |

```sql
SELECT * FROM work.v_abc WHERE risk_tier = 'A' ORDER BY suspicion_score DESC LIMIT 50;
SELECT * FROM work.finding WHERE passenger_id = 'card:…' ORDER BY severity DESC;
SELECT e.*, fl.flight_date, fl.flight_number, fl.from_airport, fl.to_airport
FROM work.evidence e
LEFT JOIN work.flight fl ON fl.flight_id = e.flight_id
WHERE e.finding_id = …;
```

## finding_type

| Код | Критерий | Вес по умолчанию |
|-----|----------|------------------|
| `high_freq` | высокая частота за 30д | 2 |
| `spike` | всплеск vs прошлые 30д | 2 |
| `route_gap` | разрыв маршрута | 2 |
| `quick_return` | туда-обратно ≤ 1 день | 2 |
| `flight_conflict` | разные маршруты в источниках | 3 |
| `id_conflict` | разные ФИО на карте | 1 |
| `doc_conflict` | разные документы Sirena | 2 |
| `card_multi_owner` | карта у нескольких профилей | 3 |
| `route_tail` | «хвост»: повтор маршрута с задержкой | 2 |

Непроверяемо: время бронирования, отмены билетов, паспорта форума (пустые). Подробности — в Word-отчёте.

## Структура

```
analysis/
  config.py          # SEVERITY, пороги shadow, статусы гипотез
  db.py
  apply_weights.py
  document_id.py     # doc_conflict
  shadow_follow.py   # route_tail
  run_analysis.py
sql/
  01_schema.sql / 02_load.sh / 03_verify.sql
  10_work_minimal.sql / 11_work_comments.sql / 13_all_hypotheses.sql
  archive/           # одноразовая сборка clean/feat
script.py            # SkyTeam YAML → CSV
scripts/build_report.py
```
>>>>>>> 4b27e99 (commit)
