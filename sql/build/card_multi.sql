TRUNCATE stage.card_multi;

INSERT INTO stage.card_multi (person_id, n, forum_ids, pointz_ids)
WITH f AS (
  SELECT meta.norm_loyalty_card(programm, number) AS card_key,
         count(DISTINCT profile_id) AS n_prof,
         string_agg(DISTINCT profile_id, ' | ' ORDER BY profile_id) AS profiles
  FROM forum.forum_cards
  GROUP BY 1
  HAVING count(DISTINCT profile_id) > 1
     AND meta.norm_loyalty_card(programm, number) IS NOT NULL
),
p AS (
  SELECT meta.norm_loyalty_card(bonus_program, card_number) AS card_key,
         count(DISTINCT user_id) AS n_users,
         string_agg(DISTINCT user_id, ' | ' ORDER BY user_id) AS users
  FROM pointz.pointz_cards
  GROUP BY 1
  HAVING count(DISTINCT user_id) > 1
     AND meta.norm_loyalty_card(bonus_program, card_number) IS NOT NULL
)
SELECT
  cp.person_id,
  coalesce(max(f.n_prof), 0) + coalesce(max(p.n_users), 0),
  string_agg(DISTINCT f.profiles, ' | '),
  string_agg(DISTINCT p.users, ' | ')
FROM stage.card_person cp
LEFT JOIN f ON f.card_key = cp.card_key
LEFT JOIN p ON p.card_key = cp.card_key
WHERE f.card_key IS NOT NULL OR p.card_key IS NOT NULL
GROUP BY cp.person_id;
