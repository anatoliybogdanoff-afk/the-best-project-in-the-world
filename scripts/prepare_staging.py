#!/usr/bin/env python3
"""Подготовка staging CSV: нормализация + склейка boarding xlsx → одна таблица."""

from __future__ import annotations

import csv
import json
import shutil
import zipfile
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "staging"
MANIFEST = STAGING / "manifest.json"

CSV_ZIP = Path("/home/thm/Загрузки/drive-download-20261016T225113Z-1-001.zip")
BOARDING_ZIP = Path(
    "/home/thm/Загрузки/Распаршенный YourBoardingPassDotAero-20261016T225250Z-1-001.zip"
)

# ASCII-имена (важно для Windows/Docker)
CSV_MAP = {
    "Маша П./profiles.csv": "forum_profiles.csv",
    "Маша П./documents.csv": "forum_documents.csv",
    "Маша П./cards.csv": "forum_cards.csv",
    "Маша П./flights.csv": "forum_flights.csv",
    "Маша В./flights.csv": "skyteam_flights.csv",
    "Маша В./flight_cards.csv": "skyteam_flight_cards.csv",
    "Арина/users.csv": "pointz_users.csv",
    "Арина/cards.csv": "pointz_cards.csv",
    "Арина/activities.csv": "pointz_activities.csv",
    "Арина/errors.csv": "pointz_errors.csv",
}

BOARDING_COLUMNS = [
    "document_title",
    "sequence_number",
    "title",
    "passenger_name",
    "class_code",
    "flight_number",
    "origin_city",
    "destination_city",
    "gate",
    "origin_airport",
    "destination_airport",
    "flight_date",
    "flight_time",
    "operator_note",
    "boarding_note",
    "seat",
    "booking_code",
    "ticket_number",
    "source_file",
    "source_sheet",
    "file_date",
    "parse_warnings",
    "raw_cells_json",
    "raw_types_json",
]


def cell_to_text(value) -> str:
    """Все значения → текст без потери ведущих нулей / N/A."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        # Excel иногда отдаёт числа; сохраняем как есть, без научной нотации для целых
        if value.is_integer():
            return str(int(value))
        return repr(value)
    return str(value)


def normalize_csv(src: Path, dst: Path) -> int:
    """utf-8-sig → utf-8, CRLF→LF, все поля текст. Возвращает число строк данных."""
    n = 0
    with src.open("r", encoding="utf-8-sig", newline="") as fin, dst.open(
        "w", encoding="utf-8", newline=""
    ) as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        header = next(reader)
        writer.writerow(header)
        for row in reader:
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))
            elif len(row) > len(header):
                row = row[: len(header)]
            writer.writerow([cell_to_text(c) for c in row])
            n += 1
    return n


def prepare_team_csvs(extract_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with zipfile.ZipFile(CSV_ZIP) as zf:
        zf.extractall(extract_dir)

    for src_rel, dst_name in CSV_MAP.items():
        src = extract_dir / src_rel
        if not src.is_file():
            raise FileNotFoundError(src)
        dst = STAGING / dst_name
        n = normalize_csv(src, dst)
        counts[dst_name] = n
        print(f"OK  {dst_name}: {n} rows")
    return counts


def merge_boarding(extract_dir: Path) -> tuple[int, int, list[str]]:
    """Склеивает лист Passes из всех *_table.xlsx в один CSV."""
    boarding_root = extract_dir / "boarding_xlsx"
    boarding_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(BOARDING_ZIP) as zf:
        names = [n for n in zf.namelist() if n.endswith("_table.xlsx") and not n.startswith("__")]
        zf.extractall(boarding_root)

    # найти все xlsx рекурсивно
    xlsx_files = sorted(boarding_root.rglob("*_table.xlsx"))
    if not xlsx_files:
        raise RuntimeError("Не найдены *_table.xlsx")

    out = STAGING / "boarding_passes.csv"
    total = 0
    per_file: dict[str, int] = {}
    warnings: list[str] = []

    with out.open("w", encoding="utf-8", newline="") as fout:
        writer = csv.writer(fout, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(BOARDING_COLUMNS)

        for path in xlsx_files:
            wb = load_workbook(path, read_only=True, data_only=True)
            if "Passes" not in wb.sheetnames:
                warnings.append(f"{path.name}: нет листа Passes")
                wb.close()
                continue
            ws = wb["Passes"]
            rows_iter = ws.iter_rows(values_only=True)
            header = [cell_to_text(c) for c in next(rows_iter)]
            if header != BOARDING_COLUMNS:
                # допускаем тот же набор в другом порядке? нет — фиксируем строго
                if set(header) != set(BOARDING_COLUMNS) or len(header) != len(BOARDING_COLUMNS):
                    warnings.append(
                        f"{path.name}: неожиданный header ({len(header)} cols)"
                    )
                # пишем в каноническом порядке по имени колонки
                col_index = {name: i for i, name in enumerate(header)}

                def map_row(raw):
                    raw = list(raw) if raw is not None else []
                    out_row = []
                    for col in BOARDING_COLUMNS:
                        i = col_index.get(col)
                        if i is None or i >= len(raw):
                            out_row.append("")
                        else:
                            out_row.append(cell_to_text(raw[i]))
                    return out_row

                n = 0
                for raw in rows_iter:
                    if raw is None or all(v is None or str(v).strip() == "" for v in raw):
                        continue
                    writer.writerow(map_row(raw))
                    n += 1
            else:
                n = 0
                for raw in rows_iter:
                    if raw is None or all(v is None or str(v).strip() == "" for v in raw):
                        continue
                    row = [cell_to_text(raw[i] if i < len(raw) else "") for i in range(len(BOARDING_COLUMNS))]
                    writer.writerow(row)
                    n += 1
            wb.close()
            per_file[path.name] = n
            total += n
            print(f"OK  boarding {path.name}: {n} rows")

    (STAGING / "boarding_per_file.json").write_text(
        json.dumps(per_file, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return total, len(xlsx_files), warnings


def main() -> None:
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)

    extract_dir = ROOT / ".extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir()

    print("=== Team CSVs ===")
    counts = prepare_team_csvs(extract_dir)

    print("\n=== Boarding merge ===")
    boarding_rows, n_files, warnings = merge_boarding(extract_dir)
    counts["boarding_passes.csv"] = boarding_rows

    manifest = {
        "tables": counts,
        "boarding_files": n_files,
        "warnings": warnings,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== MANIFEST ===")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nStaging ready: {STAGING}")


if __name__ == "__main__":
    main()
