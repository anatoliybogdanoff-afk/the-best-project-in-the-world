"""Потоковый парсер PointzAggregator XML: 3 CSV + журнал проблем.

Запуск:
    python xml_to_csv_with_errors.py PointzAggregator-AirlinesData.xml --out parsed

Исходный XML читается без изменений. Все номера карт остаются строками.
"""

# argparse отвечает за аргументы командной строки: имя XML и папку результата.
import argparse
# csv записывает таблицы с корректным экранированием запятых и кавычек.
import csv
# json помогает сохранить нестандартные поля событий, не теряя их.
import json
# Встроенная библиотека Python для разбора структуры XML.
import xml.etree.ElementTree as ET
# Counter — словарь-счётчик: сколько найдено пользователей, карт, ошибок и т.д.
from collections import Counter
# ExitStack закрывает сразу все созданные CSV-файлы в конце блока with.
from contextlib import ExitStack
# date используется только для проверки формата даты перелёта.
from datetime import date
# Path делает работу с путями к файлам независимой от ОС.
from pathlib import Path


# Безопасно читаем содержимое тега: отсутствующее значение заменяем пустой строкой.
def text_of(parent, tag):
    """Текст дочернего тега; при отсутствии — пустая строка."""
    return parent.findtext(tag, default="") or ""


# Приводим имена к единому виду, чтобы находить совпадения несмотря на регистр и пробелы.
def normalize_name(first, last):
    """Нормализованное ФИО для сравнения (регистр/лишние пробелы)."""
    return " ".join(f"{first} {last}".split()).casefold()


# Создаём CSV, записываем заголовки и возвращаем объект для добавления строк.
def csv_writer(stack, folder, filename, fields):
    # utf-8-sig удобно открывать в Excel: русские записи об ошибках не превратятся в «кракозябры».
    # newline="" нужен модулю csv для правильной записи переводов строк.
    f = stack.enter_context((folder / filename).open("w", newline="", encoding="utf-8-sig"))
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    return writer


# Главная функция: одно чтение XML -> три связанные таблицы и отдельный журнал ошибок.
def parse(xml_path, out_dir):
    # Создаём каталог для результатов, если его ещё нет. XML никуда не перемещаем и не переписываем.
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    # Справочники уже встреченных значений используются для обнаружения дублей.
    # Они хранят только краткую информацию, а не всё дерево XML.
    seen_uids = {}       # uid -> (user_id, full_name)
    seen_names = {}      # normalized FIO -> (user_id, uid, full_name)
    seen_cards = {}      # card number -> (card_id, user_id, uid)
    types = Counter()

    # Все четыре выходных файла открыты одновременно, поэтому их строки можно создавать
    # по мере обхода вложенных элементов одного пользователя.
    with ExitStack() as stack:
        # Одна строка на каждый XML-элемент <user>.
        # user_id создаётся нами, uid берётся из файла и НЕ исправляется при дублях.
        users = csv_writer(stack, out_dir, "users.csv", [
            "user_id", "uid", "first_name", "last_name"
        ])
        # Одна строка на каждую <card>; user_id — ссылка на владельца карты.
        # Номер карты всегда сохраняется строкой (например, "FB 171388778").
        cards = csv_writer(stack, out_dir, "cards.csv", [
            "card_id", "user_id", "uid", "card_number", "bonus_program", "cards_type"
        ])
        # Одна строка на <activity>; card_id — ссылка на карту.
        # uid и card_number дополнительно повторяем для удобства проверки CSV.
        activities = csv_writer(stack, out_dir, "activities.csv", [
            "activity_id", "card_id", "card_number", "uid", "activity_type",
            "activities_type", "code", "date", "departure", "arrival", "fare", "other_fields"
        ])
        # В этот CSV попадают как ошибки (ERROR), так и предупреждения (WARNING).
        # Повторяющееся ФИО с другим uid — предупреждение: это могут быть тёзки.
        errors = csv_writer(stack, out_dir, "errors.csv", [
            "severity", "error_type", "user_id", "uid", "full_name",
            "card_id", "card_number", "activity_id", "details"
        ])

        # Общая функция для записи любой проблемы в errors.csv и обновления счётчиков.
        # severity — серьёзность; error_type — машиночитаемый код проблемы.
        def report(severity, error_type, user_id="", uid="", full_name="",
                   card_id="", card_number="", activity_id="", details=""):
            counts["issues"] += 1
            counts[f"issue:{error_type}"] += 1
            errors.writerow({
                "severity": severity, "error_type": error_type,
                "user_id": user_id, "uid": uid, "full_name": full_name,
                "card_id": card_id, "card_number": card_number,
                "activity_id": activity_id, "details": details,
            })

        # Обрабатываем законченный элемент <user> и освобождаем память.
        # iterparse читает большой XML последовательно, без загрузки всего файла в память.
        # Нас интересует событие "end" для user: к этому моменту прочитаны все его карты
        # и активности, значит пользователя можно целиком обработать и затем удалить из памяти.
        iterator = ET.iterparse(xml_path, events=("start", "end"))
        # Первый элемент XML должен быть контейнером всех пользователей.
        _, root = next(iterator)
        if root.tag != "PointzAggregatorUsers":
            raise ValueError(f"Неожиданный корневой тег XML: {root.tag}")

        # Перебираем события XML-парсера; пропускаем всё кроме закрывающего </user>.
        for event, user in iterator:
            if event != "end" or user.tag != "user":
                continue

            # user_id — последовательный уникальный номер записи, даже если исходный uid повторился.
            counts["users"] += 1
            user_id = counts["users"]
            # get("uid") читает АТРИБУТ <user uid="...">, а не дочерний тег.
            uid = user.get("uid", "")             # uid хранится как строка
            # А имя и фамилия, напротив, являются атрибутами вложенного <name>.
            name = user.find("name")
            first = name.get("first", "") if name is not None else ""
            last = name.get("last", "") if name is not None else ""
            full_name = " ".join(part for part in (first, last) if part)
            normalized = normalize_name(first, last)

            # Даже пользователь без карт обязательно записывается в users.csv.
            users.writerow({"user_id": user_id, "uid": uid,
                            "first_name": first, "last_name": last})

            # uid должен быть указан и уникален; найденные проблемы только фиксируем,
            # а исходные значения сохраняем как есть.
            if not uid:
                report("ERROR", "MISSING_UID", user_id, uid, full_name)
            elif uid in seen_uids:
                earlier_id, earlier_name = seen_uids[uid]
                report("ERROR", "DUPLICATE_UID", user_id, uid, full_name,
                       details=f"Совпадение с user_id={earlier_id}, ФИО={earlier_name}")
            else:
                seen_uids[uid] = (user_id, full_name)

            # ФИО не используем как ключ: одно ФИО может принадлежать разным людям.
            # Сравнение имён проводится отдельно от проверки уникальности uid.
            if not first or not last:
                report("WARNING", "MISSING_NAME", user_id, uid, full_name)
            elif normalized in seen_names:
                earlier_id, earlier_uid, earlier_name = seen_names[normalized]
                issue = "DUPLICATE_NAME_SAME_UID" if uid == earlier_uid else "DUPLICATE_NAME_DIFFERENT_UID"
                report("WARNING", issue, user_id, uid, full_name,
                       details=f"Совпадение с user_id={earlier_id}, uid={earlier_uid}, ФИО={earlier_name}")
            else:
                seen_names[normalized] = (user_id, uid, full_name)

            # <cards/> — допустимый пустой контейнер, у пользователя просто нет карт.
            # Если <cards> вовсе отсутствует, это записывается как предупреждение.
            cards_group = user.find("cards")
            if cards_group is None:
                report("WARNING", "MISSING_CARDS_GROUP", user_id, uid, full_name)
            else:
                found_cards = cards_group.findall("card")
                if not found_cards:
                    counts["users_without_cards"] += 1

                # У одного пользователя может быть несколько карт; создаём строку для каждой.
                for card in found_cards:
                    counts["cards"] += 1
                    card_id = counts["cards"]
                    # Не приводим номер к числу: пробелы и буквенные префиксы значимы.
                    number = card.get("number", "")   # без преобразования в int!
                    cards.writerow({
                        "card_id": card_id, "user_id": user_id, "uid": uid,
                        "card_number": number,
                        "bonus_program": text_of(card, "bonusprogramm"),
                        "cards_type": cards_group.get("type", ""),
                    })

                    # Проверяем уникальность номера карты отдельно от её card_id.
                    # При совпадении фиксируем ошибку, но обе карты остаются в cards.csv.
                    if not number:
                        report("ERROR", "MISSING_CARD_NUMBER", user_id, uid,
                               full_name, card_id=card_id)
                    elif number in seen_cards:
                        earlier_card, earlier_user, earlier_uid = seen_cards[number]
                        report("ERROR", "DUPLICATE_CARD_NUMBER", user_id, uid,
                               full_name, card_id, number,
                               details=(f"Совпадение с card_id={earlier_card}, "
                                        f"user_id={earlier_user}, uid={earlier_uid}"))
                    else:
                        seen_cards[number] = (card_id, user_id, uid)

                    # <activities> объединяет события карты; его type записываем отдельно
                    # от type каждого конкретного <activity>.
                    acts_group = card.find("activities")
                    if acts_group is None:
                        continue  # карта без событий допустима
                    group_type = acts_group.get("type", "")

                    # Каждое событие получает уникальный activity_id и ссылку на card_id.
                    for activity in acts_group.findall("activity"):
                        counts["activities"] += 1
                        activity_id = counts["activities"]
                        activity_type = activity.get("type", "")
                        types[activity_type] += 1
                        code = text_of(activity, "Code")
                        flight_date = text_of(activity, "Date")

                        # Незнакомые поля не выбрасываем: складываем в JSON-строку.
                        # Остальные вложенные теги и дополнительные атрибуты сохраняем как JSON.
                        # Это защищает от потери данных, если появятся новые типы активностей.
                        extra = {child.tag: child.text or "" for child in activity
                                 if child.tag not in {"Code", "Date", "Departure", "Arrival", "Fare"}}
                        extra.update({f"@{k}": v for k, v in activity.attrib.items() if k != "type"})

                        # Записываем обычные поля события в отдельные столбцы.
                        activities.writerow({
                            "activity_id": activity_id, "card_id": card_id,
                            "card_number": number, "uid": uid,
                            "activity_type": activity_type,
                            "activities_type": group_type,
                            "code": code, "date": flight_date,
                            "departure": text_of(activity, "Departure"),
                            "arrival": text_of(activity, "Arrival"),
                            "fare": text_of(activity, "Fare"),
                            "other_fields": json.dumps(extra, ensure_ascii=False) if extra else "",
                        })

                        # Отсутствие типа — ошибка. Для Flight дополнительно проверяем
                        # обязательные поля Code/Date и корректность даты ISO YYYY-MM-DD.
                        if not activity_type:
                            report("ERROR", "MISSING_ACTIVITY_TYPE", user_id, uid,
                                   full_name, card_id, number, activity_id)
                        if activity_type == "Flight":
                            if not code or not flight_date:
                                report("WARNING", "INCOMPLETE_FLIGHT", user_id, uid,
                                       full_name, card_id, number, activity_id,
                                       "Не указан Code или Date")
                            else:
                                try:
                                    date.fromisoformat(flight_date)
                                except ValueError:
                                    report("WARNING", "BAD_FLIGHT_DATE", user_id, uid,
                                           full_name, card_id, number, activity_id,
                                           f"Некорректная дата: {flight_date}")

            # Не копим обработанных пользователей в оперативной памяти.
            # После завершения пользователя очищаем прочитанные элементы XML:
            # память не растёт пропорционально числу записей во входном файле.
            root.clear()

    # Контроль числа строк и FK через новые внутренние идентификаторы.
    # Повторно открываем созданные CSV и проверяем, что записалось ровно столько строк,
    # сколько было элементов в XML. Проверяем также ссылки на новые ID.
    with (out_dir / "users.csv").open(encoding="utf-8-sig", newline="") as f:
        exported_users = sum(1 for _ in csv.DictReader(f))
    with (out_dir / "cards.csv").open(encoding="utf-8-sig", newline="") as f:
        exported_cards = 0
        broken_user_links = 0
        for r in csv.DictReader(f):
            exported_cards += 1
            if not (1 <= int(r["user_id"]) <= counts["users"]):
                broken_user_links += 1
    with (out_dir / "activities.csv").open(encoding="utf-8-sig", newline="") as f:
        exported_events = 0
        broken_card_links = 0
        for r in csv.DictReader(f):
            exported_events += 1
            if not (1 <= int(r["card_id"]) <= counts["cards"]):
                broken_card_links += 1

    # Если какая-то строка пропала или ссылка выходит за диапазон — останавливаемся
    # с ошибкой AssertionError, а не показываем «Готово».
    assert exported_users == counts["users"]
    assert exported_cards == counts["cards"]
    assert exported_events == counts["activities"]
    assert not broken_user_links and not broken_card_links

    # Краткий результат для терминала: удобно приложить скриншот к отчёту.
    print("Готово. Исходный XML не изменён.")
    print(f"Пользователи: {counts['users']}, карты: {counts['cards']}, "
          f"события: {counts['activities']}")
    print(f"Пользователей без карт: {counts['users_without_cards']}")
    print(f"Типы событий: {dict(types)}")
    print(f"Записей в errors.csv: {counts['issues']}")
    for filename in ("users.csv", "cards.csv", "activities.csv", "errors.csv"):
        print(out_dir / filename)


# Функция для удобного запуска из терминала: python3 script.py source.xml --out folder.
def main():
    parser = argparse.ArgumentParser(description="Преобразует PointzAggregator XML в связанные CSV")
    parser.add_argument("xml", type=Path, help="Путь к исходному XML")
    parser.add_argument("--out", type=Path, default=Path("parsed_csv"), help="Папка результатов")
    args = parser.parse_args()
    parse(args.xml, args.out)


# Этот код запускается только при запуске файла, а не при импорте как модуля.
if __name__ == "__main__":
    main()
