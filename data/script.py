#!/usr/bin/env python3
"""Парсер SkyTeam-Exchange.yaml → flights.csv + flight_cards.csv.

Структура исходника: дата → рейс → карты (FF).
Без внешних зависимостей (только стандартная библиотека).
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

DATE_RE = re.compile(r"^'(\d{4}-\d{2}-\d{2})':\s*$")
FLIGHT_RE = re.compile(r"^  ([A-Z0-9]+):\s*$")
FROM_RE = re.compile(r"^    FROM:\s*(.+?)\s*$")
TO_RE = re.compile(r"^    TO:\s*(.+?)\s*$")
STATUS_RE = re.compile(r"^    STATUS:\s*(.+?)\s*$")
CARD_RE = re.compile(
    r"^      (.+?):\s*\{CLASS:\s*([A-Z0-9]+),\s*FARE:\s*([A-Z0-9]+)\}\s*$"
)
SKIP_RE = re.compile(r"^    FF:\s*$")


def parse_yaml(
    source: Path,
    flights_path: Path,
    cards_path: Path,
) -> dict:
    flight_id = 0
    cards_count = 0
    dates_count = 0
    warnings: list[str] = []
    unmatched = 0

    current_date: str | None = None
    current_flight: str | None = None
    current_from: str | None = None
    current_to: str | None = None
    current_status: str | None = None
    # Карты буферизуем до закрытия рейса (поля FROM/TO/STATUS могут идти после FF)
    pending_cards: list[tuple[str, str, str]] = []
    open_flight = False

    def flush_flight(writer_flights, writer_cards) -> None:
        nonlocal flight_id, cards_count, open_flight
        if not open_flight:
            return
        flight_id += 1
        writer_flights.writerow(
            {
                "flight_id": flight_id,
                "date": current_date,
                "flight_number": current_flight,
                "from_airport": current_from,
                "to_airport": current_to,
                "status": current_status,
            }
        )
        for card_number, travel_class, fare in pending_cards:
            cards_count += 1
            writer_cards.writerow(
                {
                    "flight_id": flight_id,
                    "card_number": card_number,
                    "class": travel_class,
                    "fare": fare,
                }
            )
        pending_cards.clear()
        open_flight = False

    flights_path.parent.mkdir(parents=True, exist_ok=True)
    cards_path.parent.mkdir(parents=True, exist_ok=True)

    with (
        source.open("r", encoding="utf-8", newline="") as src,
        flights_path.open("w", encoding="utf-8", newline="") as f_out,
        cards_path.open("w", encoding="utf-8", newline="") as c_out,
    ):
        writer_flights = csv.DictWriter(
            f_out,
            fieldnames=[
                "flight_id",
                "date",
                "flight_number",
                "from_airport",
                "to_airport",
                "status",
            ],
        )
        writer_cards = csv.DictWriter(
            c_out,
            fieldnames=["flight_id", "card_number", "class", "fare"],
        )
        writer_flights.writeheader()
        writer_cards.writeheader()

        for line_no, raw in enumerate(src, 1):
            line = raw.rstrip("\r\n")
            if not line:
                continue

            m_date = DATE_RE.match(line)
            if m_date:
                flush_flight(writer_flights, writer_cards)
                current_date = m_date.group(1)
                current_flight = None
                current_from = current_to = current_status = None
                dates_count += 1
                continue

            m_flight = FLIGHT_RE.match(line)
            if m_flight:
                flush_flight(writer_flights, writer_cards)
                current_flight = m_flight.group(1)
                current_from = current_to = current_status = None
                open_flight = True
                continue

            if SKIP_RE.match(line):
                continue

            m_from = FROM_RE.match(line)
            if m_from:
                current_from = m_from.group(1)
                continue

            m_to = TO_RE.match(line)
            if m_to:
                current_to = m_to.group(1)
                continue

            m_status = STATUS_RE.match(line)
            if m_status:
                current_status = m_status.group(1)
                continue

            m_card = CARD_RE.match(line)
            if m_card:
                # Номер карты всегда текст (не теряем пробел и ведущие нули)
                pending_cards.append(
                    (m_card.group(1), m_card.group(2), m_card.group(3))
                )
                continue

            unmatched += 1
            if len(warnings) < 20:
                warnings.append(f"строка {line_no}: нераспознано: {line[:120]}")

        flush_flight(writer_flights, writer_cards)

    return {
        "dates": dates_count,
        "flights": flight_id,
        "cards": cards_count,
        "unmatched_lines": unmatched,
        "warnings": warnings,
    }


def verify_against_source(source: Path, stats: dict) -> None:
    """Независимый подсчёт по сырому тексту (как у Маши)."""
    date_re = re.compile(r"^'\d{4}-\d{2}-\d{2}':\s*$")
    flight_re = re.compile(r"^  [A-Z0-9]+:\s*$")
    card_re = re.compile(
        r"^      .+:\s*\{CLASS:\s*[A-Z0-9]+,\s*FARE:\s*[A-Z0-9]+\}\s*$"
    )
    dates = flights = cards = 0
    with source.open("r", encoding="utf-8", newline="") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if date_re.match(line):
                dates += 1
            elif flight_re.match(line):
                flights += 1
            elif card_re.match(line):
                cards += 1

    print("\n--- НЕЗАВИСИМАЯ ПРОВЕРКА ПО СЫРОМУ ТЕКСТУ ---")
    print(f"Дат в исходнике:     {dates}  | в CSV: {stats['dates']}")
    print(f"Рейсов в исходнике:  {flights}  | в CSV: {stats['flights']}")
    print(f"Карт в исходнике:    {cards}  | в CSV: {stats['cards']}")
    ok = (
        dates == stats["dates"]
        and flights == stats["flights"]
        and cards == stats["cards"]
    )
    print("Совпадение счётчиков:", "OK" if ok else "ОШИБКА")


def show_examples(flights_path: Path, cards_path: Path, n: int = 3) -> None:
    print("\n--- ПРИМЕРЫ (первые строки) ---")
    with flights_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))[:n]
    print("\nflights.csv:")
    for row in rows:
        print(row)

    with cards_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))[:n]
    print("\nflight_cards.csv:")
    for row in rows:
        print(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Парсер SkyTeam-Exchange.yaml")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parent / "input" / "SkyTeam-Exchange.yaml",
        help="Путь к SkyTeam-Exchange.yaml",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "output",
        help="Папка для CSV",
    )
    args = parser.parse_args()

    source = args.input
    if not source.is_file():
        raise SystemExit(f"Файл не найден: {source}")

    flights_path = args.output / "flights.csv"
    cards_path = args.output / "flight_cards.csv"

    print(f"Читаю: {source}")
    print(f"Пишу:  {flights_path}")
    print(f"       {cards_path}")

    stats = parse_yaml(source, flights_path, cards_path)

    print("\n--- РЕЗУЛЬТАТ ---")
    print(f"Дат:              {stats['dates']}")
    print(f"Рейсов (flights): {stats['flights']}")
    print(f"Связей карт:      {stats['cards']}")
    print(f"Неразобранных строк: {stats['unmatched_lines']}")
    if stats["warnings"]:
        print("Предупреждения:")
        for w in stats["warnings"]:
            print(" ", w)

    verify_against_source(source, stats)
    show_examples(flights_path, cards_path)

    # Сверка первых рейсов с известным фрагментом исходника
    print("\n--- СВЕРКА С ИСХОДНИКОМ (2017-01-01 / AF1145) ---")
    with flights_path.open("r", encoding="utf-8", newline="") as f:
        first = next(csv.DictReader(f))
    print("Первый рейс CSV:", first)
    print(
        "Ожидание: date=2017-01-01, flight_number=AF1145, "
        "from=SVO, to=CDG, status=LANDED"
    )
    with cards_path.open("r", encoding="utf-8", newline="") as f:
        first_card = next(csv.DictReader(f))
    print("Первая карта CSV:", first_card)
    print("Ожидание: card_number='FB 520518073', class=Y, fare=YRSTFN")


if __name__ == "__main__":
    main()
