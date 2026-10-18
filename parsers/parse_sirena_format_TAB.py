
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

SIRENA_FIELDS = [('PaxName',0,60),('PaxBirthDate',60,72),('DepartDate',72,84),('DepartTime',84,96),('ArrivalDate',96,108),('ArrivalTime',108,120),('FlightCode',120,126),('Sh',126,132),('From',132,138),('Dest',138,144),('Code',144,150),('e-Ticket',150,168),('TravelDoc',168,180),('Seat',180,186),('Meal',186,192),('TrvCls',192,198),('Fare',198,204),('Baggage',204,216),('PaxAdditionalInfo',216,276),('AgentInfo',276,336)]

BOARDING_FIELDS = 'PassengerFirstName PassengerSecondName PassengerLastName PassengerSex PassengerBirthDate PassengerDocument BookingCode TicketNumber Baggage FlightDate FlightTime FlightNumber CodeShare Destination'.split()

META=['record_id','source_file','source_line','quality_flags']

MISSING={'','N/A','NA','NULL','NOT PRESENTED'}

def writer(path,fields):
    h=path.open('w',encoding='utf-8',newline='')
    w=csv.DictWriter(h,fieldnames=fields);w.writeheader()
    return h,w

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def parse_source(path,out):
    kind = 'sirena'
    fields=BOARDING_FIELDS if kind=='boarding' else [n for n,_,_ in SIRENA_FIELDS]
    h,w=writer(out/f'{kind}_records.csv',fields+META+(['raw_line'] if kind=='sirena' else []))
    eh,ew=writer(out/f'{kind}_errors.csv',['source_file','source_line','reason','raw_record'])
    stats={'input_file':path.name,'sha256':sha(path),'physical_lines':0,'blank_lines':0,'candidate_records':0,'saved_records':0,'rejected_records':0,'missing_by_field':Counter(),'flags':Counter(),'exact_duplicate_records':0,'flight_date_min':None,'flight_date_max':None,'ambiguous_birth_dates':0}
    seen=set();dates=[]
    def consume(row,line,raw,flags):
        vals=[row[n] for n in fields]
        digest=hashlib.sha256(json.dumps(vals,ensure_ascii=False).encode()).digest()
        if digest in seen:stats['exact_duplicate_records']+=1
        seen.add(digest)
        for n in fields:
            if row[n].strip().upper() in MISSING:stats['missing_by_field'][n]+=1
        dn='FlightDate' if kind=='boarding' else 'DepartDate'
        dv=row[dn].strip()
        if dv.upper() not in MISSING:
            try:dates.append(date.fromisoformat(dv).isoformat())
            except ValueError:flags.append('invalid_departure_date')
        for n in (['FlightTime'] if kind=='boarding' else ['DepartTime','ArrivalTime']):
            v=row[n].strip()
            if v.upper() not in MISSING and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',v):flags.append('invalid_'+n)
        ticket='TicketNumber' if kind=='boarding' else 'e-Ticket'
        if row[ticket].strip().upper() not in MISSING and not row[ticket].strip().isdigit():flags.append('non_digit_ticket')
        if kind=='boarding':
            v=row['PassengerBirthDate'].split('/')
            if len(v)==3 and all(x.isdigit() for x in v) and 1<=int(v[0])<=12 and 1<=int(v[1])<=12 and v[0]!=v[1]:stats['ambiguous_birth_dates']+=1
        stats['flags'].update(flags)
        row.update(record_id=f'{kind}:{line}',source_file=path.name,source_line=line,quality_flags=';'.join(flags))
        if kind=='sirena':row['raw_line']=raw
        w.writerow(row);stats['saved_records']+=1
    with path.open(encoding='utf-8-sig',newline='') as src:
        if kind=='boarding':
            reader=csv.reader(src,delimiter=';',strict=True)
            header=next(reader)
            if header!=fields:raise ValueError('Unexpected BoardingData header; inspect before parsing')
            previous=reader.line_num;stats['physical_lines']=previous
            for vals in reader:
                start=previous+1;previous=reader.line_num;stats['physical_lines']=previous
                if not vals or (len(vals)==1 and not vals[0].strip()):stats['blank_lines']+=1;continue
                stats['candidate_records']+=1
                if len(vals)!=len(fields):
                    ew.writerow(dict(source_file=path.name,source_line=start,reason=f'expected {len(fields)} fields, got {len(vals)}',raw_record=json.dumps(vals,ensure_ascii=False)));stats['rejected_records']+=1;continue
                consume(dict(zip(fields,vals)),start,None,[])
        else:
            header=next(src).rstrip('\r\n');stats['physical_lines']=1
            for n,a,b in SIRENA_FIELDS:
                if n=='Sh':continue  
                if header[a:a+len(n)]!=n:raise ValueError(f'Unexpected Sirena header position for {n}')
            for lineno,line in enumerate(src,2):
                stats['physical_lines']=lineno;raw=line.rstrip('\r\n')
                if not raw.strip():stats['blank_lines']+=1;continue
                stats['candidate_records']+=1
                if len(raw)!=336:
                    ew.writerow(dict(source_file=path.name,source_line=lineno,reason=f'expected width 336, got {len(raw)}',raw_record=raw));stats['rejected_records']+=1;continue
                row={n:raw[a:b].strip() for n,a,b in SIRENA_FIELDS}
                flight=re.fullmatch(r'([A-Z0-9]{2}\d+)(YES|NO)',raw[120:132].strip())
                if not flight:
                    ew.writerow(dict(source_file=path.name,source_line=lineno,reason='invalid_combined_flight_codeshare',raw_record=raw));stats['rejected_records']+=1;continue
                row['FlightCode'],row['Sh']=flight.groups()
                consume(row,lineno,raw,[])
    h.close();eh.close()
    if dates:stats['flight_date_min'],stats['flight_date_max']=min(dates),max(dates)
    assert stats['candidate_records']==stats['saved_records']+stats['rejected_records']
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
    parser = argparse.ArgumentParser(description='Обработка Sirena')
    parser.add_argument("--input", type=Path, required=True, help="Путь к исходному файлу")
    parser.add_argument("--output", type=Path, required=True, help="Отдельная папка результата; одноимённые файлы перезаписываются")
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error("Исходный файл не найден")
    args.output.mkdir(parents=True, exist_ok=True)
    stats = parse_source(args.input, args.output)
    save_reports(args.output, stats, {'sirena_records.csv': stats["saved_records"]}, 'Обработка Sirena', 'Текст читается по фиксированным позициям, длина записи 336 символов. Блок 120:132 разбирается как номер рейса + YES/NO. Крайние пробелы полей удаляются; raw_line сохраняет исходную строку. Номера документов и билетов остаются текстом. Повторы сохраняются.')

if __name__ == "__main__":
    main()
