# Catch the Spies


**Пересобрать витрины с нуля** (сырые `forum` / `skyteam` / `pointz` **не трогает**):

```bash
cd /home/thm/skyteam_parser
.venv/bin/python -m analysis.build_person_wide
```

Пересоздаёт: `meta.norm_loyalty_card`, `feat.*`, `stage.*`.

Проверка после сборки:

```bash
.venv/bin/python scripts/verify_feat.py
```

| В `person_features` | В `person_evidence` |
|---------------------|---------------------|
| `spike_windows_n = 0` | `spike_*` = **NULL** (критерий не сработал) |
| `spike_windows_n > 0` | `spike_*` **заполнены** id рейсов пика |
| `high_freq_windows_n = 0` | `high_freq_*` = NULL |
| всегда | `card_numbers`, `first_flight_date` / `last_flight_date` заполнены |

Смотри человека с `spike_windows_n > 0` — там spike-колонки не пустые.  
Пустые `high_freq_*` при нулевом high_freq — ожидаемо.

```sql
SELECT f.person_id, f.spike_windows_n, f.high_freq_windows_n,
       e.spike_skyteam_flight_ids, e.high_freq_skyteam_flight_ids
FROM feat.person_features f
JOIN feat.person_evidence e USING (person_id)
WHERE f.spike_windows_n > 0
LIMIT 5;
```

## Почему `meta` «пустая»

В `meta` **нет таблиц** — только функция `meta.norm_loyalty_card(program, number)`.  
В DBeaver: Schema → **meta** → **Functions** (не Tables).  
Нужна, чтобы SQL и Python одинаково нормализовали карты (`FB 123`).

## Схемы

| Схема | Содержимое |
|-------|------------|
| `forum` / `skyteam` / `pointz` | Сырьё (не дропается сборкой) |
| `meta` | Функция `norm_loyalty_card` |
| `stage` | Промежуточные таблицы сборки |
| `feat` | `person_features` + `person_evidence` + `person_card` + `card_conflict` |

**Карта у нескольких аккаунтов:** склейка всё равно даёт один `person_id` (кластер), но детали не теряются — таблица `feat.card_conflict` + флаг `card_multi_profile_n` (приоритетный finding, не шум).

## SQL в IDE

Критерии лежат в **`sql/build/*.sql`** — открывай их, подсветка SQL работает.  
Python только подставляет `__THR__` и т.п. и вызывает `execute_script`.

### Зачем `execute_script`

`asyncpg` за один `conn.execute(...)` принимает **одну** команду.  
Файл вида `TRUNCATE …; INSERT …;` режется по `;` и выполняется по шагам.  
Это не «магия», а ограничение драйвера.

## Docker (готовая БД для команды)

Сборка для девочек: **`/home/thm/Загрузки/spy_db_ready.zip`** (~263 MB).  
Внутри: `docker-compose.yml` (Postgres **17**), `dump/spy_flights.dump`, restore-скрипт, инструкция Windows.
Витрины: `feat.person`, `feat.person_features`, `feat.flight`, `stage.flight_unique` (+ страны).

```bash
unzip spy_db_ready.zip && cd spy_db_ready   # или распаковать в папку
docker compose up -d
bash scripts/verify_docker_db.sh            # 35 таблиц, строки как в manifest
```

Подробнее: `README_DOCKER.txt`, `КАК_ЗАПУСТИТЬ_НА_WINDOWS.txt`.

## Пороги

`analysis/config.py` — единственное место с порогами критериев.

## Документы (Sirena)

Finding по Sirena traveldoc (только дубли **одного** типа): `doc_rf_conflict_n` (10 цифр),
`doc_foreign_conflict_n` (9 цифр), `doc_other_conflict_n`. Пара РФ+загран — не конфликт.

## Хвост маршрута

`route_tail_n` — средние OD (`SHADOW_ROUTE_*`).  
`route_tail_rare_n` — редкие OD (`SHADOW_RARE_ROUTE_*`, сейчас 5–40 рейсов на маршрут).

## Код

```
analysis/build_person_wide.py   # вход сборки
analysis/config.py
analysis/db.py                  # asyncpg + execute_script
analysis/sql_load.py            # load_sql("….sql")
analysis/person/                # identity, flights, criteria, …
sql/20_person_tables.sql        # DDL feat
sql/21_stage_tables.sql         # DDL stage
sql/22_helpers.sql              # meta.norm_loyalty_card
sql/build/*.sql                 # запросы критериев (для IDE)
scripts/verify_feat.py          # сверка после сборки
```
