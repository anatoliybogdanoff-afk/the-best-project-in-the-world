"""
Конфиг критериев и весов (severity).
Меняйте веса здесь — затем: python -m analysis.run_analysis
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Вес находки (severity) → суммируется в suspicion_score / категория A-B-C
# Чем больше число — тем сильнее вклад в score (можно > 3)
# ---------------------------------------------------------------------------
SEVERITY: dict[str, int] = {
    "high_freq": 2,  # высокая частота перелётов за 30 дней
    "spike": 2,  # всплеск vs предыдущие 30 дней
    "route_gap": 2,  # разрыв маршрута (прилёт ≠ следующий вылет)
    "quick_return": 5,  # туда-обратно за ≤ 1 день
    "flight_conflict": 3,  # разные маршруты в источниках на один рейс/дату
    "id_conflict": 1,  # разные ФИО (часто транслит)
    "doc_conflict": 2,  # разные документы Sirena на одной FF-карте
    "card_multi_owner": 5,  # одна карта — несколько профилей
    "route_tail": 5,  # «хвост»: повтор чужого маршрута с задержкой
}

# Человекочитаемые названия для отчёта / README
FINDING_LABELS: dict[str, str] = {
    "high_freq": "1. Высокая частота перелётов",
    "spike": "2. Всплеск активности",
    "route_gap": "3. Противоречия / разрыв маршрута",
    "quick_return": "3b. Быстрый возврат туда-обратно",
    "flight_conflict": "4. Расхождение сведений о перелёте",
    "id_conflict": "5a. Противоречия имён",
    "doc_conflict": "5b. Противоречия документов (Sirena)",
    "card_multi_owner": "6. Конфликт владельцев карты",
    "route_tail": "7. Совпадение маршрутов во времени («хвост»)",
}

# Статус гипотезы для отчёта: confirmed_signal | partial | not_checkable
HYPOTHESIS_STATUS: dict[str, str] = {
    "high_freq": "confirmed_signal",
    "spike": "confirmed_signal",
    "route_gap": "partial",  # факт разрыва есть; «невозможно» без TZ — нет
    "quick_return": "confirmed_signal",
    "flight_conflict": "partial",  # часто шум forum↔skyteam
    "id_conflict": "confirmed_signal",
    "doc_conflict": "confirmed_signal",
    "card_multi_owner": "confirmed_signal",
    "route_tail": "confirmed_signal",
    "booking_time_match": "not_checkable",  # поля времени брони нет
    "ticket_cancel": "not_checkable",
    "forum_empty_docs": "not_checkable",  # все document_number пустые
}

# Параметры «хвоста» (route_tail)
SHADOW = {
    "delay_min_days": 1,
    "delay_max_days": 7,
    "min_repeats": 2,
    "min_route_flights": 5,
    "max_route_flights": 120,
    "top_pairs": 100,
}

# Пороги A/B/C считаются в SQL-view по перцентилям score;
# high_freq порог (рейсов за 30д) зашит в sql/10 при первичной сборке:
HIGH_FREQ_MIN_FLIGHTS_30D = 8
