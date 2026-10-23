-- Evidence для route_gap / quick_return по id парных рейсов.
-- Плейсхолдеры: __PREFIX__ __STAGE_TBL__

UPDATE feat.person_evidence e SET
  __PREFIX___skyteam_flight_ids = x.sky,
  __PREFIX___forum_flight_ids = x.frm,
  __PREFIX___pointz_activity_ids = x.ptz,
  __PREFIX___sirena_record_ids = x.sir
FROM (
  WITH hit AS (
    SELECT DISTINCT g.person_id, p.src, p.src_id
    FROM __STAGE_TBL__ g
    JOIN stage.flight_event p ON p.person_id = g.person_id
      AND (
        (p.flight_date = g.prev_date AND p.flight_number = g.prev_fn)
        OR (p.flight_date = g.flight_date AND p.flight_number = g.flight_number)
      )
  )
  SELECT person_id,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint)
      FILTER (WHERE src = 'skyteam') AS sky,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint)
      FILTER (WHERE src = 'forum') AS frm,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint)
      FILTER (WHERE src = 'pointz') AS ptz,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint)
      FILTER (WHERE src = 'sirena') AS sir
  FROM hit
  GROUP BY person_id
) x
WHERE e.person_id = x.person_id;
