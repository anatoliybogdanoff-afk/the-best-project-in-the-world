-- Evidence id-списки строго по пикам (не по envelope w0..w1).
-- Плейсхолдеры: __PREFIX__ __PEAKS_TABLE__ __WINDOWS_TABLE__

UPDATE feat.person_evidence e SET
  __PREFIX___from_date = t.w0,
  __PREFIX___to_date = t.w1,
  __PREFIX___skyteam_flight_ids  = x.sky,
  __PREFIX___forum_flight_ids    = x.frm,
  __PREFIX___pointz_activity_ids = x.ptz,
  __PREFIX___sirena_record_ids   = x.sir
FROM __WINDOWS_TABLE__ t
LEFT JOIN (
  SELECT person_id,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint)
      FILTER (WHERE src = 'skyteam') AS sky,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint)
      FILTER (WHERE src = 'forum') AS frm,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint)
      FILTER (WHERE src = 'pointz') AS ptz,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint)
      FILTER (WHERE src = 'sirena') AS sir
  FROM (
    SELECT DISTINCT pk.person_id, p.src, p.src_id
    FROM __PEAKS_TABLE__ pk
    JOIN stage.flight_event p
      ON p.person_id = pk.person_id
     AND p.flight_date BETWEEN pk.window_start AND pk.window_end
  ) hit
  GROUP BY person_id
) x ON x.person_id = t.person_id
WHERE e.person_id = t.person_id;
