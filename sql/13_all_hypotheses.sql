-- Сводка гипотез (DBeaver / psql). Где смотреть: work.finding + work.evidence + work.v_abc

\echo '======= СВОДКА finding_type ======='
SELECT finding_type, count(*) AS findings,
       count(DISTINCT passenger_id) AS passengers,
       min(severity) AS sev
FROM work.finding
GROUP BY 1
ORDER BY findings DESC;

\echo '======= A/B/C ======='
SELECT risk_tier, count(*),
       min(suspicion_score) AS score_min,
       max(suspicion_score) AS score_max
FROM work.v_abc
GROUP BY 1 ORDER BY 1;

\echo '======= TOP-A ======='
SELECT passenger_id, suspicion_score, findings_n, tier_reason
FROM work.v_abc
WHERE risk_tier = 'A'
ORDER BY suspicion_score DESC
LIMIT 20;

\echo '======= ПРИМЕРЫ ПО ТИПАМ ======='
SELECT finding_type, finding_id, passenger_id, left(detail, 100) AS detail, status
FROM (
  SELECT *, row_number() OVER (PARTITION BY finding_type ORDER BY finding_id) AS rn
  FROM work.finding
) t
WHERE rn <= 3
ORDER BY finding_type, finding_id;

\echo '======= FORUM DOCS (ожидаем nonempty=0) ======='
SELECT count(*) AS total,
       count(*) FILTER (WHERE coalesce(trim(document_number),'') <> '') AS nonempty
FROM forum_documents;

\echo '======= ROUTE_TAIL ======='
SELECT finding_id, passenger_id, detail, period_start, period_end
FROM work.finding
WHERE finding_type = 'route_tail'
ORDER BY finding_id
LIMIT 15;
