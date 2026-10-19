#!/usr/bin/env python3
"""Собирает reports/DATA_report_minimal.docx для команды."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from analysis.config import FINDING_LABELS, HYPOTHESIS_STATUS, SEVERITY
from analysis.db import cursor

OUT = ROOT / "reports" / "DATA_report_minimal.docx"
DOWNLOADS = Path.home() / "Загрузки" / "DATA_report_minimal.docx"

STATUS_RU = {
    "confirmed_signal": "да — сигнал в БД",
    "partial": "частично",
    "not_checkable": "нет — данных нет",
}

EXTRA_NOTES = {
    "route_gap": "разрыв есть; «невозможно долететь» без точного TZ не доказываем",
    "flight_conflict": "часто шум forum↔skyteam, не шпионаж",
    "booking_time_match": "нет timestamp брони в источниках",
    "ticket_cancel": "нет полей отмены/возврата",
    "forum_empty_docs": "forum_documents пустые; документы — через doc_conflict (Sirena)",
}


def _h(doc: Document, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def _p(doc: Document, text: str) -> None:
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.size = Pt(11)


def _code(doc: Document, text: str) -> None:
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.name = "Consolas"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
    run.font.size = Pt(9)


def _table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for i, h in enumerate(headers):
        t.rows[0].cells[i].text = h
        for p in t.rows[0].cells[i].paragraphs:
            for r in p.runs:
                r.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = val


def fetch_stats() -> tuple[dict[str, int], dict[str, int], str]:
    with cursor() as cur:
        cur.execute(
            "SELECT finding_type, count(*), count(DISTINCT passenger_id) "
            "FROM work.finding GROUP BY 1"
        )
        by_type = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        # Человек с несколькими типами, включая route_tail — удобный разбор
        cur.execute(
            """
            SELECT passenger_id
            FROM work.finding
            WHERE finding_type = 'route_tail'
            GROUP BY passenger_id
            ORDER BY count(*) DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row:
            example_id = row[0]
        else:
            cur.execute(
                """
                SELECT passenger_id FROM work.v_abc
                WHERE risk_tier = 'A'
                ORDER BY suspicion_score DESC
                LIMIT 1
                """
            )
            example_id = cur.fetchone()[0]
    counts = {k: v[0] for k, v in by_type.items()}
    pax = {k: v[1] for k, v in by_type.items()}
    return counts, pax, example_id


def build() -> Path:
    n, pax, example_id = fetch_stats()
    doc = Document()

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run("Catch the Spies — DATA")
    r.bold = True
    r.font.size = Pt(16)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = sub.add_run("Маша Валова · схема work · гипотезы")
    sr.font.size = Pt(11)
    sr.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    # --- 1.1 схема ---
    _h(doc, "1.1. Схема work")
    _table(
        doc,
        ["Таблица", "Смысл"],
        [
            [
                "passenger",
                "Кто это: одна карта лояльности (программа SU/FB/KE/DT + номер). "
                "Ключ: passenger_id вида card:FB 123…",
            ],
            [
                "passenger_name",
                "Как зовут: ФИО из forum и/или pointz. Несколько строк, если источники расходятся.",
            ],
            [
                "flight",
                "Куда летал: уникальный рейс (дата, номер, откуда→куда) этой карты.",
            ],
            [
                "flight_source",
                "Откуда узнали про рейс: skyteam, forum, pointz или sirena "
                "(один рейс может быть в нескольких источниках).",
            ],
            [
                "finding",
                "Что нашли по критерию: тип (finding_type), текст, вес severity, статус проверки.",
            ],
            [
                "evidence",
                "Почему так думаем: ссылка на конкретный рейс (flight_id) или имя/заметку. "
                "Отсюда удобно идти проверять человека.",
            ],
            [
                "v_abc",
                "Кого смотреть первым: сумма severity → категории A (топ), B, C.",
            ],
        ],
    )

    _p(
        doc,
        "Веса severity — analysis/config.py. После смены: "
        "python -m analysis.run_analysis (v_abc обновится сам).",
    )

    # --- гипотезы ---
    _h(doc, "1.2. Гипотезы / finding_type")
    rows = []
    for key in SEVERITY:
        st = HYPOTHESIS_STATUS.get(key, "")
        note = EXTRA_NOTES.get(key, "")
        conf = STATUS_RU.get(st, st)
        if note:
            conf = f"{conf} ({note})"
        rows.append(
            [
                key,
                FINDING_LABELS.get(key, key),
                str(SEVERITY[key]),
                str(n.get(key, 0)),
                str(pax.get(key, 0)),
                conf,
            ]
        )
    _table(
        doc,
        [
            "finding_type",
            "Критерий",
            "вес",
            "находок",
            "пассажиров",
            "подтвердилось?",
        ],
        rows,
    )

    _h(doc, "Не проверяем (в данных нет полей)", level=2)
    for key in ("booking_time_match", "ticket_cancel", "forum_empty_docs"):
        _p(doc, f"• {key} — {EXTRA_NOTES[key]}")

    # --- SQL ---
    _h(doc, "1.3. Как смотреть: от evidence к человеку")
    _p(
        doc,
        "Логика: v_abc → список finding человека → evidence → рейс / источник / имя. "
        f"Пример пассажира (топ A на момент отчёта): {example_id}",
    )

    _p(doc, "① Кандидаты A:")
    _code(
        doc,
        "SELECT passenger_id, suspicion_score, findings_n, tier_reason\n"
        "FROM work.v_abc\n"
        "WHERE risk_tier = 'A'\n"
        "ORDER BY suspicion_score DESC\n"
        "LIMIT 50;",
    )

    _p(doc, "② Все критерии по одному человеку:")
    _code(
        doc,
        f"SELECT finding_id, finding_type, title, detail, severity, status,\n"
        f"       period_start, period_end\n"
        f"FROM work.finding\n"
        f"WHERE passenger_id = '{example_id}'\n"
        f"ORDER BY severity DESC, finding_type;",
    )

    _p(doc, "③ Сводка по типам у него:")
    _code(
        doc,
        f"SELECT finding_type, count(*), sum(severity) AS score_part\n"
        f"FROM work.finding\n"
        f"WHERE passenger_id = '{example_id}'\n"
        f"GROUP BY finding_type\n"
        f"ORDER BY score_part DESC;",
    )

    _p(doc, "④ От evidence: рейсы + откуда взялись + имена (главный разбор):")
    _code(
        doc,
        f"SELECT\n"
        f"  f.finding_id,\n"
        f"  f.finding_type,\n"
        f"  f.severity,\n"
        f"  f.detail,\n"
        f"  e.kind,\n"
        f"  e.label,\n"
        f"  fl.flight_id,\n"
        f"  fl.flight_date,\n"
        f"  fl.flight_number,\n"
        f"  fl.from_airport,\n"
        f"  fl.to_airport,\n"
        f"  fs.source\n"
        f"FROM work.finding f\n"
        f"JOIN work.evidence e ON e.finding_id = f.finding_id\n"
        f"LEFT JOIN work.flight fl ON fl.flight_id = e.flight_id\n"
        f"LEFT JOIN work.flight_source fs ON fs.flight_id = fl.flight_id\n"
        f"WHERE f.passenger_id = '{example_id}'\n"
        f"ORDER BY f.severity DESC, f.finding_id, e.evidence_id;",
    )

    _p(doc, "⑤ Имена и профиль:")
    _code(
        doc,
        f"SELECT * FROM work.passenger WHERE passenger_id = '{example_id}';\n"
        f"SELECT * FROM work.passenger_name WHERE passenger_id = '{example_id}';\n"
        f"SELECT * FROM work.flight\n"
        f"WHERE passenger_id = '{example_id}'\n"
        f"ORDER BY flight_date, flight_number;",
    )

    _p(
        doc,
        "finding ≠ «шпион». status по умолчанию needs_check — "
        "после разбора ставьте confirmed или false_alarm.",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    try:
        DOWNLOADS.parent.mkdir(parents=True, exist_ok=True)
        doc.save(DOWNLOADS)
    except OSError:
        pass
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"OK → {path}")
