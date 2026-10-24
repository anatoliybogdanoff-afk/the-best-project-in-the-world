
from __future__ import annotations

import csv
import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import re
import shutil

import psycopg
from typing import Annotated
from pydantic import WithJsonSchema
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.import_service import (
    load_staging_to_database,
    run_import,
    validate_file_content,
)
from src.analysis.scoring import load_config
from src.analysis.service import analyze_database, assess_person

PROJECT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", str(PROJECT_DIR / "frontend")))
OUTPUT_DIR = Path(os.getenv(
    "ANALYSIS_OUTPUT_DIR",
    str(PROJECT_DIR / "outputs" / "web-runs")
))
CONFIG_PATH = os.getenv("SPY_CONFIG_PATH") or None
DATABASE_URL = os.getenv("SPY_DATABASE_URL") or os.getenv("DATABASE_URL")

BinaryUploadFile = Annotated[
    UploadFile,
    WithJsonSchema({
        "type": "string",
        "format": "binary",
    }),
]

app = FastAPI(title="Catch the Spies API")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOCK = threading.RLock()
ROWS: list[dict[str, Any]] = []
SUMMARY = None
RESULTS_DIR = None
JOB = None
CONFIG = load_config(CONFIG_PATH)


def require_dsn():
    if not DATABASE_URL:
        raise HTTPException(
            status_code=503,
            detail="Не задан SPY_DATABASE_URL или DATABASE_URL."
        )
    return DATABASE_URL


def number(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_results(folder: Path):
    global ROWS, SUMMARY, RESULTS_DIR, CONFIG

    summary_file = folder / "summary.json"
    ranking_file = folder / "ranking.csv"
    method_file = folder / "method.json"

    if not all(p.is_file() for p in (
        summary_file, ranking_file, method_file
    )):
        return False

    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    method = json.loads(method_file.read_text(encoding="utf-8"))
    rows = []

    with ranking_file.open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        for row in csv.DictReader(stream):
            names = [
                row.get("name_forum") or "",
                row.get("name_sirena") or "",
                row.get("name_pointz") or "",
            ]
            name = next(
                (n for n in names if n.strip()),
                f"Профиль № {row['person_id']}"
            )
            name = name.replace("|", ";").split(";")[0].strip()

            raw_identity = row.get("identity_resolved")
            identity = (
                None if raw_identity in (None, "")
                else raw_identity.lower() in ("true", "t", "1", "yes")
            )

            rows.append({
                "person_id": int(row["person_id"]),
                "name": name or f"Профиль № {row['person_id']}",
                "score": number(row.get("score")),
                "score_min": number(row.get("score_min")),
                "score_max": number(row.get("score_max")),
                "identity_resolved": identity,
                "identity_kind": row.get("identity_kind"),
                "triggered_criteria": [
                    x for x in
                    (row.get("triggered_criteria") or "").split(";")
                    if x
                ],
                "_search": (
                    " ".join(names) + " " + row["person_id"]
                ).casefold(),
            })

    with LOCK:
        ROWS = rows
        SUMMARY = summary
        RESULTS_DIR = folder
        CONFIG = method

    return True


def run_calculation(job_id):
    global JOB

    try:
        folder = OUTPUT_DIR / (
            datetime.now().strftime("%Y%m%d-%H%M%S-") + job_id
        )
        folder.mkdir(parents=True, exist_ok=True)

        analyze_database(
            require_dsn(),
            folder,
            config_path=CONFIG_PATH
        )

        if not read_results(folder):
            raise RuntimeError("Не удалось прочитать результаты.")

        with LOCK:
            JOB = {
                "id": job_id,
                "status": "done",
                "message": "Рейтинг готов"
            }

    except Exception:
        with LOCK:
            JOB = {
                "id": job_id,
                "status": "error",
                "message": (
                    "Не удалось выполнить расчёт. Проверьте PostgreSQL, "
                    "таблицу feat.person_features и конфигурацию правил."
                )
            }


@app.get("/api/health")
def health():
    try:
        with psycopg.connect(
            require_dsn(), connect_timeout=3
        ) as conn:
            conn.read_only = True
            database = conn.execute(
                "SELECT current_database()"
            ).fetchone()[0]

        return {
            "status": "ok",
            "connected": True,
            "database": database
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Не удалось подключиться к PostgreSQL."
        )


@app.get("/api/status")
def status():
    try:
        with psycopg.connect(
            require_dsn(), connect_timeout=3
        ) as conn:
            conn.read_only = True
            database = conn.execute(
                "SELECT current_database()"
            ).fetchone()[0]

        connected = True
        message = None

    except Exception:
        connected = False
        database = None
        message = "Нет подключения к PostgreSQL. Проверьте Docker."

    with LOCK:
        summary = SUMMARY
        job = dict(JOB) if JOB else None

    result = {
        "connected": connected,
        "database": database,
        "has_results": summary is not None,
        "people": summary.get("people") if summary else None,
        "job": job,
    }
    if message:
        result["message"] = message
    return result


@app.get("/api/config")
def get_config():
    return CONFIG


@app.post("/api/calculate", status_code=202)
def calculate():
    global JOB
    require_dsn()

    with LOCK:
        if JOB and JOB.get("status") == "running":
            return dict(JOB)

        job_id = uuid.uuid4().hex[:12]
        JOB = {
            "id": job_id,
            "status": "running",
            "message": "Считаем рейтинг пассажиров"
        }

    threading.Thread(
        target=run_calculation,
        args=(job_id,),
        daemon=True
    ).start()

    return dict(JOB)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with LOCK:
        if not JOB or JOB.get("id") != job_id:
            raise HTTPException(
                status_code=404,
                detail="Расчёт не найден."
            )
        return dict(JOB)


@app.get("/api/results")
def results(
    q: str = Query(default="", max_length=200),
    filter: str = "all",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    sort: str = "score",
):
    with LOCK:
        rows = list(ROWS)
        summary = SUMMARY

    if summary is None:
        raise HTTPException(
            status_code=409,
            detail="Сначала запустите расчёт."
        )

    if filter == "signals":
        rows = [r for r in rows if r["triggered_criteria"]]
    elif filter == "identity":
        rows = [
            r for r in rows
            if r["identity_resolved"] is False
        ]

    query = q.casefold().strip()
    if query:
        rows = [r for r in rows if query in r["_search"]]

    if sort == "score_asc":
        rows.sort(key=lambda r: (
            r["score"] is None, r["score"] or 0, r["person_id"]
        ))
    elif sort == "name":
        rows.sort(key=lambda r: (
            r["name"].casefold(), r["person_id"]
        ))
    else:
        rows.sort(key=lambda r: (
            r["score"] is None, -(r["score"] or 0), r["person_id"]
        ))

    items = [
        {k: v for k, v in row.items() if not k.startswith("_")}
        for row in rows[offset:offset + limit]
    ]

    distribution = summary.get("score_distribution", {})
    with_signals = sum(
        int(count) for score, count in distribution.items()
        if number(score) is not None and float(score) > 0
    )

    return {
        "items": items,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "summary": {
            "people": summary.get("people", len(ROWS)),
            "with_signals": with_signals,
            "identity_review": summary.get("needs_identity_review", 0),
            "created_at": summary.get("created_at_utc"),
            "max_score": max(
                (number(s) or 0 for s in distribution),
                default=0
            ),
        },
    }


@app.get("/api/people/{person_id}")
def person(person_id: int):
    try:
        return assess_person(
            require_dsn(),
            person_id,
            config_path=CONFIG_PATH
        )
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Пассажир не найден."
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Не удалось получить карточку пассажира."
        )


@app.get("/api/export")
def export():
    if RESULTS_DIR is None:
        raise HTTPException(
            status_code=409,
            detail="Сначала выполните расчёт."
        )

    file = RESULTS_DIR / "ranking.csv"
    if not file.is_file():
        raise HTTPException(
            status_code=404,
            detail="Файл результатов не найден."
        )

    return FileResponse(
        file,
        media_type="text/csv",
        filename="catch-the-spies-ranking.csv"
    )


# Все загрузки сохраняются в папку проекта, независимо от каталога запуска.
_DEFAULT_IMPORT_ROOT = PROJECT_DIR / "data" / "uploads"

IMPORT_ROOT = Path(
    os.getenv("IMPORT_ROOT", str(_DEFAULT_IMPORT_ROOT))
).expanduser()

if not IMPORT_ROOT.is_absolute():
    IMPORT_ROOT = PROJECT_DIR / IMPORT_ROOT

IMPORT_ROOT = IMPORT_ROOT.resolve()
IMPORT_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".xml",
    ".json",
    ".yaml",
    ".yml",
    ".tab",
    ".xlsx",
    ".csv",
    ".pdf",
    ".zip",
}

MAX_FILES = 50
MAX_FILE_SIZE = 50 * 1024 * 1024 * 1024              # 50 МБ на файл
MAX_TOTAL_SIZE = 100 * 1024 * 1024 * 1024            # 150 МБ на один запрос
IMPORT_JOBS: dict[str, dict[str, Any]] = {}


def run_import_job(job_id: str, job_dir: Path) -> None:
    """Фоновый запуск: HTTP-ответ не ждёт окончания разбора файлов."""
    try:
        report = run_import(job_dir)
        with LOCK:
            IMPORT_JOBS[job_id] = report
    except Exception as exc:
        with LOCK:
            IMPORT_JOBS[job_id] = {
                "job_id": job_id,
                "status": "failed",
                "message": str(exc),
            }


@app.post("/api/imports", status_code=202)
async def import_files(files: list[BinaryUploadFile] = File(...)):
    """Принимает несколько файлов и сохраняет их для последующей обработки."""

    if not files:
        raise HTTPException(
            status_code=400,
            detail="Выберите хотя бы один файл.",
        )

    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Можно загрузить не более {MAX_FILES} файлов за раз.",
        )

    prepared = []

    # Сначала проверяем имена и форматы всех файлов.
    for file in files:
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="У одного из файлов отсутствует имя.",
            )

        # Убираем возможный путь к файлу из присланного имени.
        original_name = file.filename.replace("\\", "/").rsplit("/", 1)[-1]
        extension = Path(original_name).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Формат файла {original_name} не поддерживается.",
            )

        prepared.append((file, original_name, extension))

    job_id = str(uuid.uuid4())
    job_dir = IMPORT_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=False)

    saved_files = []
    total_size = 0

    try:
        for number, (file, original_name, extension) in enumerate(
            prepared, start=1
        ):
            safe_name = re.sub(
                r"[^A-Za-zА-Яа-яЁё0-9._-]",
                "_",
                original_name,
            )

            # Номер предотвращает перезапись файлов с одинаковыми именами.
            target = job_dir / f"{number:02d}_{safe_name}"
            file_size = 0

            with target.open("wb") as output:
                while True:
                    chunk = await file.read(1024 * 1024)

                    if not chunk:
                        break

                    file_size += len(chunk)
                    total_size += len(chunk)

                    if file_size > MAX_FILE_SIZE:
                        raise HTTPException(
                            status_code=413,
                            detail=f"Файл {original_name} превышает 50 МБ.",
                        )

                    if total_size > MAX_TOTAL_SIZE:
                        raise HTTPException(
                            status_code=413,
                            detail="Общий размер файлов превышает 150 МБ.",
                        )

                    output.write(chunk)

            if file_size == 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Файл {original_name} пустой.",
                )

            try:
                validate_file_content(target, extension)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            saved_files.append({
                "original_name": original_name,
                "saved_as": target.name,
                "extension": extension,
                "size_bytes": file_size,
            })

    except Exception:
        # Если сохранение не удалось, не оставляем неполную загрузку.
        shutil.rmtree(job_dir, ignore_errors=True)
        raise

    finally:
        for file in files:
            await file.close()

    with LOCK:
        IMPORT_JOBS[job_id] = {
            "job_id": job_id,
            "status": "processing",
            "file_count": len(saved_files),
        }

    threading.Thread(
        target=run_import_job,
        args=(job_id, job_dir),
        daemon=True,
    ).start()

    return {
        "job_id": job_id,
        "status": "processing",
        "file_count": len(saved_files),
        "files": saved_files,
        "message": (
            "Файлы сохранены, парсеры запущены. Проверяйте статус по "
            "/api/imports/{job_id}."
        ),
    }


@app.get("/api/imports/{job_id}")
def import_status(job_id: str):
    """Статус загрузки и результаты каждого запущенного парсера."""
    with LOCK:
        result = IMPORT_JOBS.get(job_id)
    if result:
        return result

    report_file = IMPORT_ROOT / job_id / "import_report.json"
    if report_file.is_file():
        return json.loads(report_file.read_text(encoding="utf-8"))

    raise HTTPException(status_code=404, detail="Импорт не найден.")


@app.post("/api/imports/{job_id}/load")
def load_import_to_database(job_id: str):
    report_file = IMPORT_ROOT / job_id / "import_report.json"

    if not report_file.is_file():
        raise HTTPException(
            status_code=404,
            detail="Import report not found",
        )

    report = json.loads(report_file.read_text(encoding="utf-8"))

    # Разрешаем загрузку только после полного успешного разбора.
    if report.get("status") != "completed":
        raise HTTPException(
            status_code=409,
            detail=(
                "Загрузка в PostgreSQL запрещена: "
                "не все файлы успешно обработаны. "
                "Проверьте import_report.json."
            ),
        )

    # Проверяем, что каждый файл попал в staging.
    if not report.get("files") or any(
        item.get("status") != "staged"
        for item in report["files"]
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Не все файлы попали в staging. "
                "Сначала исправьте ошибки парсеров."
            ),
        )

    # Загружаем подготовленные данные в PostgreSQL.
    try:
        load_result = load_staging_to_database(
            IMPORT_ROOT / job_id / "staging",
            require_dsn(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка загрузки в PostgreSQL: {exc}",
        ) from exc

    report["database_load"] = load_result
    report_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return report


# Статику подключаем последней, после API-маршрутов.
if FRONTEND_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )

# Статику подключаем последней, после API-маршрутов.
if FRONTEND_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend"
    )
