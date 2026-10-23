-- Схема meta: НЕ таблицы, а SQL-функции сборки.
-- В DBeaver смотри Schema → meta → Functions (папка Tables будет пустой — так и должно быть).
-- При сборке функция пересоздаётся из этого файла (analysis.person.sql_helpers).

CREATE SCHEMA IF NOT EXISTS meta;
COMMENT ON SCHEMA meta IS
  'Вспомогательные SQL-функции (не таблицы). Главная: meta.norm_loyalty_card — нормализация карт лояльности.';

CREATE OR REPLACE FUNCTION meta.norm_loyalty_card(program text, number text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE
    WHEN nullif(btrim(number), '') IS NULL THEN NULL
    WHEN btrim(number) ~* '^[A-Za-z]{2}[[:space:]:#]*[0-9]+$'
      THEN upper(substring(btrim(number) from '([A-Za-z]{2})'))
           || ' '
           || substring(btrim(number) from '([0-9]+)')
    WHEN length(
           upper(
             CASE btrim(coalesce(program, ''))
               WHEN 'Flying Blue' THEN 'FB'
               WHEN 'Korean Air SKYPASS' THEN 'KE'
               WHEN 'Aeroflot Bonus' THEN 'SU'
               WHEN 'Delta SkyMiles' THEN 'DT'
               ELSE btrim(coalesce(program, ''))
             END
           )
         ) = 2
         AND regexp_replace(btrim(number), '\D', '', 'g') <> ''
      THEN upper(
             CASE btrim(coalesce(program, ''))
               WHEN 'Flying Blue' THEN 'FB'
               WHEN 'Korean Air SKYPASS' THEN 'KE'
               WHEN 'Aeroflot Bonus' THEN 'SU'
               WHEN 'Delta SkyMiles' THEN 'DT'
               ELSE btrim(coalesce(program, ''))
             END
           )
           || ' '
           || regexp_replace(btrim(number), '\D', '', 'g')
    ELSE NULL
  END
$$;

COMMENT ON FUNCTION meta.norm_loyalty_card(text, text) IS
  'Нормализация карты к виду «FB 171388778». Совпадает с analysis.cards.norm_card.';
