"""
Все пороги сборки витрин.

Меняешь здесь → пересобираешь:
  python -m analysis.build_person_wide

В criteria/flights не должно быть «магических» чисел критериев —
только ссылки на эти константы.

Обрезки списков evidence (LIMIT 80 / 500 / …) здесь нет намеренно:
тихая усечка id ломает проверку «есть счётчик — есть доказательства».
"""

from __future__ import annotations

# ----- окна по времени (дни) -----
WINDOW_DAYS_30 = 30

# ----- высокая частота -----
HIGH_FREQ_MIN_FLIGHTS_30D = 8
HIGH_FREQ_PEAK_GAP_DAYS = WINDOW_DAYS_30

# ----- всплеск -----
SPIKE_MIN_RATIO = 2.0
SPIKE_MIN_NOW = 5
SPIKE_PEAK_GAP_DAYS = WINDOW_DAYS_30

# ----- туда-обратно -----
# Соседние рейсы: обратный OD, задержка ≤ N дней.
# Пары «тот же номер рейса в тот же день» отбрасываются в SQL (шум источников).
QUICK_RETURN_MAX_DAYS = 1

# ----- «хвост» (route_tail) -----
# Средние маршруты: окно 5–120 рейсов на OD, ≥2 повтора пары leader×маршрут.
# (REP≥3 на всём окне почти пусто; REP=5 обнулял колонку.)
SHADOW_DELAY_MIN_DAYS = 1
SHADOW_DELAY_MAX_DAYS = 7
SHADOW_MIN_REPEATS = 2
SHADOW_ROUTE_MIN_FLIGHTS = 5
SHADOW_ROUTE_MAX_FLIGHTS = 120

# Редкие маршруты (отдельная колонка route_tail_rare_n):
# окно 5–40 рейсов на OD. REP=2 (как средний минимум), но на редком OD
# два повтора уже сильный сигнал; REP≥3 на 5–40 в дампе = 0 человек.
SHADOW_RARE_MIN_REPEATS = 2
SHADOW_RARE_ROUTE_MIN_FLIGHTS = 5
SHADOW_RARE_ROUTE_MAX_FLIGHTS = 40

# ----- служебное -----
# Пустой код и мусорный REA (в route_seq сравнение через UPPER).
ROUTE_IGNORE_AIRPORTS = ("", "REA")

POINTZ_PROGRAM_MAP = {
    "Flying Blue": "FB",
    "Korean Air SKYPASS": "KE",
    "Aeroflot Bonus": "SU",
    "Delta SkyMiles": "DT",
}

BUILD_WORK_MEM = "256MB"
