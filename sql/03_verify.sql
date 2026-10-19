-- Быстрая проверка после загрузки
SELECT 'forum_profiles' AS table_name, count(*) AS rows FROM forum_profiles
UNION ALL SELECT 'forum_documents', count(*) FROM forum_documents
UNION ALL SELECT 'forum_cards', count(*) FROM forum_cards
UNION ALL SELECT 'forum_flights', count(*) FROM forum_flights
UNION ALL SELECT 'skyteam_flights', count(*) FROM skyteam_flights
UNION ALL SELECT 'skyteam_flight_cards', count(*) FROM skyteam_flight_cards
UNION ALL SELECT 'pointz_users', count(*) FROM pointz_users
UNION ALL SELECT 'pointz_cards', count(*) FROM pointz_cards
UNION ALL SELECT 'pointz_activities', count(*) FROM pointz_activities
UNION ALL SELECT 'pointz_errors', count(*) FROM pointz_errors
UNION ALL SELECT 'boarding_passes', count(*) FROM boarding_passes
ORDER BY 1;

-- Примеры (шпионский поиск руками)
SELECT 'skyteam sample' AS what, flight_id, date, flight_number, from_airport, to_airport
FROM skyteam_flights LIMIT 3;

SELECT 'card sample' AS what, flight_id, card_number, class, fare
FROM skyteam_flight_cards LIMIT 3;

SELECT 'boarding sample' AS what, passenger_name, flight_number, ticket_number, file_date
FROM boarding_passes LIMIT 3;
