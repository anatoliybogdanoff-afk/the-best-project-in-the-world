
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.import_service import load_staging_to_database


UPLOAD_ID = "fbf64ddb-8469-4710-9b21-e6ae875166d0"
STAGING = ROOT / "data" / "uploads" / UPLOAD_ID / "staging"

REQUIRED_CSV = [
    "forum_profiles.csv",
    "forum_documents.csv",
    "forum_cards.csv",
    "forum_flights.csv",
    "skyteam_flights.csv",
    "skyteam_flight_cards.csv",
    "timetable_records.csv",
    "sirena_records.csv",
    "boarding_passes.csv",
    "boarding_data.csv",
    "pointz_users.csv",
    "pointz_cards.csv",
    "pointz_activities.csv",
    "pointz_errors.csv",
]

RAW_TABLES = [
    ("forum", "forum_profiles"),
    ("forum", "forum_documents"),
    ("forum", "forum_cards"),
    ("forum", "forum_flights"),
    ("skyteam", "skyteam_flights"),
    ("skyteam", "skyteam_flight_cards"),
    ("skyteam", "timetable_records"),
    ("skyteam", "sirena_records"),
    ("skyteam", "boarding_passes"),
    ("skyteam", "boarding_data"),
    ("pointz", "pointz_users"),
    ("pointz", "pointz_cards"),
    ("pointz", "pointz_activities"),
    ("pointz", "pointz_errors"),
]


def connection_args(dbname: str, args) -> dict:
    return {
        "host": args.host,
        "port": args.port,
        "dbname": dbname,
        "user": args.user,
        "password": args.password,
        "connect_timeout": 10,
    }


def check_project_files():
    required = [
        ROOT / "data" / "sql" / "01_schema.sql",
        ROOT / "data" / "sql" / "22_helpers.sql",
        ROOT / "data" / "sql" / "20_person_tables.sql",
        ROOT / "data" / "sql" / "21_stage_tables.sql",
        ROOT / "data" / "analysis" / "build_person_wide.py",
    ]

    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Не найдены необходимые файлы проекта:\n"
            + "\n".join(missing)
        )

    missing_csv = [
        name for name in REQUIRED_CSV
        if not (STAGING / name).is_file()
    ]

    if missing_csv:
        raise FileNotFoundError(
            f"В папке {STAGING} отсутствуют CSV:\n"
            + "\n".join(missing_csv)
            + "\nСначала закончи парсинг и подготовь эти файлы."
        )


def create_empty_database(args):
    if args.db == "spy_flights":
        raise RuntimeError(
            "Отказ: скрипт не должен изменять основную БД spy_flights."
        )

    with psycopg.connect(
        **connection_args("postgres", args),
        autocommit=True,
    ) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (args.db,),
        ).fetchone()

        if exists:
            raise RuntimeError(
                f"База {args.db} уже существует. "
                "Скрипт ничего не удалял и не изменял. "
                "Укажи другое имя через --db."
            )

        conn.execute(
            sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(args.db)
            )
        )

    print(f"Создана новая база: {args.db}")


def apply_sql_files(args):
    paths = [
        ROOT / "data" / "sql" / "01_schema.sql",
        ROOT / "data" / "sql" / "22_helpers.sql",
    ]

    with psycopg.connect(
        **connection_args(args.db, args)
    ) as conn:
        with conn.transaction():
            for path in paths:
                print(f"Применяю {path.relative_to(ROOT)}")
                conn.execute(path.read_text(encoding="utf-8-sig"))



def load_raw_data(args):
    import csv
    import tempfile
    import shutil

    dsn = make_conninfo(**connection_args(args.db, args))

    print(f"\nЗагружаю готовые CSV из:\n{STAGING}")

    # Создаём временную копию CSV. Исходный staging не меняем.
    with tempfile.TemporaryDirectory(prefix="spy_csv_fixed_") as temp:
        temp_dir = Path(temp)

        for source in STAGING.glob("*.csv"):
            destination = temp_dir / source.name

            if source.name == "boarding_passes.csv":
                print("Исправляю разделитель boarding_passes.csv: ; -> ,")

                with source.open(
                    "r", encoding="utf-8-sig", newline=""
                ) as fin, destination.open(
                    "w", encoding="utf-8", newline=""
                ) as fout:
                    reader = csv.reader(fin, delimiter=";")
                    writer = csv.writer(fout)

                    for row in reader:
                        writer.writerow(row)
            else:
                shutil.copy2(source, destination)

        results = load_staging_to_database(temp_dir, dsn)

    print("\nРезультат загрузки:")
    for item in results:
        print(
            f"  {item.get('table', '?')}: "
            f"получено {item.get('received_rows', '?')}, "
            f"добавлено {item.get('inserted_rows', '?')}"
        )



def run_analytics(args):
    env = os.environ.copy()

    # Убираем DSN, чтобы он случайно не направил аналитику
    # в основную базу.
    env.pop("SPY_PG_DSN", None)

    env.update({
        "SPY_PG_HOST": args.host,
        "SPY_PG_PORT": str(args.port),
        "SPY_PG_DB": args.db,
        "SPY_PG_USER": args.user,
        "SPY_PG_PASSWORD": args.password,
    })

    print("\nЗапускаю построение аналитических витрин...")
    subprocess.run(
        [sys.executable, "-m", "data.analysis.build_person_wide"],
        cwd=ROOT,
        env=env,
        check=True,
    )


def verify_database(args):
    print("\nПроверка количества строк:")

    with psycopg.connect(
        **connection_args(args.db, args)
    ) as conn:
        for schema, table in RAW_TABLES:
            count = conn.execute(
                sql.SQL("SELECT count(*) FROM {}.{}").format(
                    sql.Identifier(schema),
                    sql.Identifier(table),
                )
            ).fetchone()[0]

            print(f"  {schema}.{table}: {count:,}")

        for schema, table in [
            ("feat", "person_features"),
            ("feat", "person_evidence"),
            ("feat", "person"),
            ("feat", "flight"),
        ]:
            exists = conn.execute(
                "SELECT to_regclass(%s)",
                (f"{schema}.{table}",),
            ).fetchone()[0]

            if exists is None:
                print(f"  НЕ НАЙДЕНА: {schema}.{table}")
                continue

            count = conn.execute(
                sql.SQL("SELECT count(*) FROM {}.{}").format(
                    sql.Identifier(schema),
                    sql.Identifier(table),
                )
            ).fetchone()[0]

            print(f"  {schema}.{table}: {count:,}")


def main():
    parser = argparse.ArgumentParser(
        description="Создание тестовой БД из готовых staging CSV"
    )
    parser.add_argument(
        "--db",
        default="spy_flights_rebuild",
        help="Имя новой БД; по умолчанию spy_flights_rebuild",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("SPY_PG_HOST", "127.0.0.1"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("SPY_PG_PORT", "5434")),
    )
    parser.add_argument(
        "--user",
        default=os.getenv("SPY_PG_USER", "spy"),
    )
    parser.add_argument(
        "--password",
        default=os.getenv("SPY_PG_PASSWORD", "spy"),
    )
    args = parser.parse_args()

    try:
        print("=== Проверка подготовленных файлов ===")
        check_project_files()

        print(f"Папка CSV: {STAGING}")
        print(f"Целевая база: {args.db}")
        print(f"PostgreSQL: {args.host}:{args.port}")

        print("\n=== Создание базы ===")
        create_empty_database(args)

        print("\n=== Создание исходных схем ===")
        apply_sql_files(args)

        print("\n=== Загрузка CSV ===")
        load_raw_data(args)

        with psycopg.connect(
            **connection_args(args.db, args)
        ) as conn:
            conn.execute("ANALYZE")

        print("\n=== Аналитика ===")
        run_analytics(args)

        print("\n=== Финальная проверка ===")
        verify_database(args)

        print("\nГОТОВО.")
        print(f"База данных: {args.db}")
        print("Основная база spy_flights этим скриптом не изменялась.")
        return 0

    except Exception as exc:
        print(f"\nОШИБКА: {exc}", file=sys.stderr)
        print(
            "Если база уже создана, она оставлена для диагностики. "
            "Скрипт автоматически её не удаляет.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
