-- Проверка после загрузки (схемы источников)
SELECT 'forum.forum_profiles' AS table_name, count(*) AS rows FROM forum.forum_profiles
UNION ALL SELECT 'forum.forum_documents', count(*) FROM forum.forum_documents
UNION ALL SELECT 'forum.forum_cards', count(*) FROM forum.forum_cards
UNION ALL SELECT 'forum.forum_flights', count(*) FROM forum.forum_flights
UNION ALL SELECT 'skyteam.skyteam_flights', count(*) FROM skyteam.skyteam_flights
UNION ALL SELECT 'skyteam.skyteam_flight_cards', count(*) FROM skyteam.skyteam_flight_cards
UNION ALL SELECT 'skyteam.sirena_records', count(*) FROM skyteam.sirena_records
UNION ALL SELECT 'skyteam.boarding_passes', count(*) FROM skyteam.boarding_passes
UNION ALL SELECT 'pointz.pointz_users', count(*) FROM pointz.pointz_users
UNION ALL SELECT 'pointz.pointz_cards', count(*) FROM pointz.pointz_cards
UNION ALL SELECT 'pointz.pointz_activities', count(*) FROM pointz.pointz_activities
UNION ALL SELECT 'pointz.pointz_errors', count(*) FROM pointz.pointz_errors
ORDER BY 1;

SELECT 'skyteam sample' AS what, flight_id, date, flight_number, from_airport, to_airport
FROM skyteam.skyteam_flights LIMIT 3;

SELECT 'card sample' AS what, flight_id, card_number, class, fare
FROM skyteam.skyteam_flight_cards LIMIT 3;

SELECT 'boarding sample' AS what, passenger_name, flight_number, ticket_number, file_date
FROM skyteam.boarding_passes LIMIT 3;
