
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

def writer(path,fields):
    h=path.open('w',encoding='utf-8',newline='')
    w=csv.DictWriter(h,fieldnames=fields);w.writeheader()
    return h,w

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

MONTHS={s:i+1 for i,s in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split())}

ROW=re.compile(r'^(\d{2}\s+[A-Z][a-z]{2})\s*-\s*(\d{2}\s+[A-Z][a-z]{2})\s+([1-7\s]+?)\s+(\d{2}:\d{2})\s+(\d{2}:\d{2})(?:\s*(\+-?\d+|-\d+))?\s+([A-Z0-9]{2}\d+\*?)\s+(\S+)\s+(\d+H\d+M|\d+H|\d+M)\s*$')

TF=['origin_airport','destination_airport','origin_label','destination_label','validity_start_raw','validity_end_raw','validity_start','validity_end','days_raw','days_sunday_1','departure_local','arrival_local','arrival_day_offset','flight_number_raw','flight_number','codeshare_marker','aircraft','travel_time_raw','operator']

def column_lines(words,middle,col):
    selected=sorted((v for v in words if (v[0]<middle)==(col==1)),key=lambda v:(v[3],v[0]))
    groups=[]
    for v in selected:
        if not groups or abs(v[3]-groups[-1][0])>2.5:groups.append([v[3],[]])
        groups[-1][1].append(v)
    return [' '.join(v[4] for v in sorted(g,key=lambda v:v[0])) for _,g in groups]

def timetable(path,out,limit=None):
    import fitz
    doc=fitz.open(path)
    count=min(len(doc),limit or len(doc))
    stats={'input_file':path.name,'sha256':sha(path),'pages_total':len(doc),'pages_processed':count,'coverage_start':'2018-11-01','coverage_end':'2019-01-31','applicable_to_2017':False,'candidate_rows':0,'parsed_rows':0,'rejected_rows':0,'pages_with_candidates':0,'no_service_notices':0,'operator_lines':0,'unattached_operator_lines':0,'route_context_errors':0,'date_errors':0}
    first=doc[0].get_text()
    if not re.search(r'01 Nov 2018\s+through\s+31 Jan 2019',first):raise ValueError('Timetable coverage changed; year inference must be reviewed')
    (out/'timetable_reading_notes.txt').write_text('\n\n'.join(doc[i].get_text() for i in range(4)),encoding='utf-8')
    h,w=writer(out/'timetable_records.csv',TF+['schedule_id','source_file','source_page','source_column','source_line','raw_line'])
    eh,ew=writer(out/'timetable_errors.csv',['source_page','source_column','source_line','reason','raw_line'])
    unique={}
    def emit(row,page,col,line,raw):
        key=tuple(row[n] for n in TF)
        if key not in unique:unique[key]={'schedule_id':f'schedule:{len(unique)+1}','occurrences':0,'first_source_page':page}
        u=unique[key];u['occurrences']+=1
        w.writerow(dict(row,schedule_id=u['schedule_id'],source_file=path.name,source_page=page,source_column=col,source_line=line,raw_line=raw))
        stats['parsed_rows']+=1
    route_context={1:('','','',''),2:('','','','')}
    pending_by_column={1:None,2:None}
    for i in range(4,count):
        page=doc[i];has=False;words=page.get_text('words')

        for col,(left,right) in enumerate([(0,page.rect.width/2),(page.rect.width/2,page.rect.width)],1):
            lines=column_lines(words,page.rect.width/2,col)
            origin,dest,ol,dl=route_context[col];pending=pending_by_column[col]
            for ln,raw in enumerate(lines,1):
                text=' '.join(raw.split())
                m=re.match(r'^(FROM|TO):\s*(.*?)\s+([A-Z0-9]{3})$',text)
                if m:
                    if m[1]=='FROM':
                        if pending:emit(*pending);pending=None
                        ol,origin=m[2],m[3];dest=dl=''
                    else:dl,dest=m[2],m[3]
                    continue
                if text.startswith('Operated by:'):
                    stats['operator_lines']+=1
                    if pending:pending[0]['operator']=text.split(':',1)[1].strip()
                    else:stats['unattached_operator_lines']+=1
                    continue
                if 'Consult your travel agent' in text:stats['no_service_notices']+=1
                if not re.match(r'^\d{2}\s+[A-Z][a-z]{2}\s*-',text):continue
                has=True;stats['candidate_rows']+=1
                if pending:emit(*pending);pending=None
                m=ROW.fullmatch(text)
                reason=''
                if not m:reason='schedule_row_pattern_mismatch'
                elif not(origin and dest):reason='missing_route_context';stats['route_context_errors']+=1
                if reason:
                    ew.writerow(dict(source_page=i+1,source_column=col,source_line=ln,reason=reason,raw_line=raw));stats['rejected_rows']+=1;continue
                a,b,days,dep,arr,offset,flight,aircraft,duration=m.groups()
                def dt(s):
                    day,mon=s.split();month=MONTHS[mon]
                    return date(2018 if month>=11 else 2019,month,int(day)).isoformat()
                try:start,end=dt(a),dt(b)
                except ValueError:
                    ew.writerow(dict(source_page=i+1,source_column=col,source_line=ln,reason='invalid_validity_date',raw_line=raw));stats['rejected_rows']+=1;continue
                if start>end or start<'2018-11-01' or end>'2019-01-31':stats['date_errors']+=1
                row=dict(zip(TF,[origin,dest,ol,dl,a,b,start,end,days,''.join(days.split()),dep,arr,int((offset or '0').replace('+-','-')),flight,flight.rstrip('*'),str(flight.endswith('*')).lower(),aircraft,duration,'']))
                pending=(row,i+1,col,ln,raw)
            pending_by_column[col]=pending
            route_context[col]=(origin,dest,ol,dl)
        if has:stats['pages_with_candidates']+=1
        if (i+1)%2000==0:print(f'PDF {i+1}/{count}: {stats["parsed_rows"]} records',flush=True)
    for pending in pending_by_column.values():
        if pending:emit(*pending)
    h.close();eh.close();doc.close()
    uh,uw=writer(out/'timetable_unique.csv',TF+['schedule_id','occurrences','first_source_page'])
    for key,u in unique.items():uw.writerow(dict(zip(TF,key),**u))
    uh.close()
    stats['unique_schedule_rows']=len(unique)
    stats['repeated_schedule_rows']=stats['parsed_rows']-len(unique)
    assert stats['candidate_rows']==stats['parsed_rows']+stats['rejected_rows']
    assert sum(u['occurrences'] for u in unique.values())==stats['parsed_rows']
    return stats

def save_reports(output, stats, counts, title, notes):
    checks = {}
    for name, expected in counts.items():
        with (output / name).open(encoding="utf-8", newline="") as stream:
            actual = sum(1 for _ in csv.DictReader(stream))
        checks[name] = {"expected": expected, "actual": actual, "passed": expected == actual}
        if actual != expected:
            raise RuntimeError(f"Количество строк не совпало: {name}")
    (output / "report.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "verification.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    text = [f"# {title}", "", notes, "", "## Проверка сохранённых таблиц", "", "| Таблица | Ожидалось | Прочитано | Совпало |", "|---|---:|---:|---|"]
    for name, check in checks.items():
        text.append(f"| {name} | {check['expected']} | {check['actual']} | {'Да' if check['passed'] else 'Нет'} |")
    text.extend(["", "## Показатели обработки", "", "```json", json.dumps(stats, ensure_ascii=False, indent=2), "```", "", "Количество строк сверено повторным чтением CSV. Это не проверка достоверности всех сведений источника. Общие ID пассажиров не назначались."])
    (output / "report.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print(f"Готово. Результаты: {output.resolve()}")
    print(json.dumps(checks, ensure_ascii=False, indent=2))

def main():
    parser = argparse.ArgumentParser(description="Извлечение таблиц расписания SkyTeam")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Отдельная папка результата; одноимённые файлы перезаписываются")
    parser.add_argument("--max-pages", type=int, help="Для пробного запуска: число страниц от начала документа")
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error("Исходный PDF не найден")
    if args.max_pages is not None and args.max_pages < 4:
        parser.error("Для пробного запуска укажите не менее 4 страниц")
    args.output.mkdir(parents=True, exist_ok=True)
    stats = timetable(args.input, args.output, args.max_pages)
    save_reports(args.output, stats, {"timetable_records.csv": stats["parsed_rows"], "timetable_unique.csv": stats["unique_schedule_rows"]}, "Обработка расписания SkyTeam", 'PDF-расписание покрывает 2018-11-01 — 2019-01-31 и не применяется к поездкам 2017 года. Строки извлекаются по координатам отдельно для двух колонок; маршрут и оператор переносятся через границы страниц. Сохраняется полная таблица и уникальные строки с количеством вхождений. source_line — номер восстановленной строки. Время местное, 1 — воскресенье. Исходное +-1 преобразуется в смещение дня -1. Параметр --max-pages означает пробный неполный разбор.')

if __name__ == "__main__":
    main()
