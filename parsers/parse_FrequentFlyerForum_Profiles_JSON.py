import json
import pandas as pd

with open('FrequentFlyerForum-Profiles.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

profiles_data = []
flights_data = []
cards_data = []
documents_data = []

for profile in data.get('Forum Profiles', []):
    profile_id = profile.get('NickName')

    real_name = profile.get('Real Name')
    if real_name is None:
        real_name = {}

    profiles_data.append({
        'profile_id': profile_id,
        'first_name': real_name.get('First Name'),
        'last_name': real_name.get('Last Name'),
        'sex': profile.get('Sex')
    })

    for flight in profile.get('Registered Flights', []):
        arr = flight.get('Arrival', {})
        dep = flight.get('Departure', {})

        flights_data.append({
            'profile_id': profile_id,
            'flight_date': flight.get('Date'),
            'flight_number': flight.get('Flight'),
            'codeshare': flight.get('Codeshare'),
            'arr_city': arr.get('City'),
            'arr_airport': arr.get('Airport'),
            'arr_country': arr.get('Country'),
            'dep_city': dep.get('City'),
            'dep_airport': dep.get('Airport'),
            'dep_country': dep.get('Country')
        })


    for card in profile.get('Loyality Programm', []):
        cards_data.append({
            'profile_id': profile_id,
            'number': str(card.get('Number')),
            'status': card.get('Status'),
            'programm': card.get('programm')
        })


    for doc in profile.get('Travel Documents', []):
        passports = doc.get('Passports')
        documents_data.append({
            'profile_id': profile_id,
            'document_type': 'Passport',
            'document_number': str(passports) if passports is not None else None
        })


print(f"Собрано профилей: {len(profiles_data)}")
print(f"Собрано перелетов: {len(flights_data)}")
print(f"Собрано карт: {len(cards_data)}")
print(f"Собрано документов: {len(documents_data)}")


df_profiles = pd.DataFrame(profiles_data)
df_flights = pd.DataFrame(flights_data)
df_cards = pd.DataFrame(cards_data)
df_documents = pd.DataFrame(documents_data)


df_profiles.to_csv('profiles.csv', index=False, encoding='utf-8')
df_flights.to_csv('flights.csv', index=False, encoding='utf-8')
df_cards.to_csv('cards.csv', index=False, encoding='utf-8')
df_documents.to_csv('documents.csv', index=False, encoding='utf-8')

with open('FrequentFlyerForum-Profiles.json', 'r', encoding='utf-8') as f:
    text = f.read()
    print('\n--- НЕЗАВИСИМАЯ ПРОВЕРКА ПО СЫРОМУ ТЕКСТУ ---')
    print(f'Ключ "NickName": встречается {text.count("NickName")} раз')
    print(f'Ключ "Flight": встречается {text.count('"Flight":')} раз')
    print(f'Ключ "programm": встречается {text.count("programm")} раз')
    print(f'Ключ "Passports": встречается {text.count("Passports")} раз')

print("\n--- ПРИМЕРЫ ДАННЫХ (ПЕРВЫЕ 2 СТРОКИ) ---")
print("\nТаблица Профилей:")
print(df_profiles.head(2).to_string())

print("\nТаблица Перелетов:")
print(df_flights.head(2).to_string())

print("\nТаблица Карт лояльности:")
print(df_cards.head(2).to_string())

print("\nТаблица Документов:")
print(df_documents.head(2).to_string())