from pathlib import Path
import time
import os
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[1]
UPLOAD = ROOT / "data" / "uploads" / "fbf64ddb-8469-4710-9b21-e6ae875166d0"
STAGING = UPLOAD / "staging"

REQUIRED = [
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


def main():
    print("Ожидаю завершения парсинга текущего задания.")
    print("Исходники повторно разбираться не будут.")
    print(f"Папка результатов: {STAGING}")
    print("Для остановки нажми Ctrl+C.\n")

    while True:
        missing = [
            name for name in REQUIRED
            if not (STAGING / name).is_file()
        ]

        if not missing:
            break

        print(
            f"Пока отсутствует CSV: {len(missing)} из {len(REQUIRED)}"
        )
        print("Ожидаю 30 секунд...")
        time.sleep(30)

    print("\nВсе 14 CSV найдены.")
    print("Перед загрузкой необходимо проверить итоговый статус задания.")
    print("Скрипт остановлен на безопасной проверке.")
    print("База данных не создавалась и не изменялась.")
    print(
        "Когда сайт покажет завершение парсинга, "
        "пришли мне итоговый статус и отчёт."
    )


if __name__ == "__main__":
    main()
