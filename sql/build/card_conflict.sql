-- Конфликтные карты: ≥2 forum-профиля и/или ≥2 pointz-user на одном card_key.
-- Пишем в feat.card_conflict (по одной строке на карту) — детали не теряются при склейке.

INSERT INTO feat.card_conflict (
  card_key, person_id,
  n_forum_profiles, n_pointz_users,
  forum_profile_ids, pointz_user_ids
)
WITH f AS (
  SELECT meta.norm_loyalty_card(programm, number) AS card_key,
         count(DISTINCT profile_id)::int AS n_prof,
         string_agg(DISTINCT profile_id, ' | ' ORDER BY profile_id) AS profiles
  FROM forum.forum_cards
  WHERE meta.norm_loyalty_card(programm, number) IS NOT NULL
  GROUP BY 1
  HAVING count(DISTINCT profile_id) > 1
),
p AS (
  SELECT meta.norm_loyalty_card(bonus_program, card_number) AS card_key,
         count(DISTINCT user_id)::int AS n_users,
         string_agg(DISTINCT user_id, ' | ' ORDER BY user_id) AS users
  FROM pointz.pointz_cards
  WHERE meta.norm_loyalty_card(bonus_program, card_number) IS NOT NULL
  GROUP BY 1
  HAVING count(DISTINCT user_id) > 1
),
keys AS (
  SELECT card_key FROM f
  UNION
  SELECT card_key FROM p
)
SELECT
  k.card_key,
  cp.person_id,
  coalesce(f.n_prof, 0),
  coalesce(p.n_users, 0),
  f.profiles,
  p.users
FROM keys k
JOIN stage.card_person cp USING (card_key)
LEFT JOIN f USING (card_key)
LEFT JOIN p USING (card_key);
