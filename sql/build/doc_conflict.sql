-- Конфликт документов Sirena (traveldoc).
-- Источники привязки к person_id:
--   1) FF# → stage.card_person
--   2) нормализованный traveldoc → stage.person_anchor (sirena_doc)
-- Тип по числу цифр: 10 = паспорт РФ, 9 = загран, иначе other.
-- Finding: только ≥2 разных номера внутри одного типа (RF / foreign / other).

TRUNCATE stage.doc_conflict;

INSERT INTO stage.doc_conflict (
  person_id,
  n_docs, docs, ids,
  n_rf, rf_docs, rf_ids,
  n_foreign, foreign_docs, foreign_ids,
  n_other, other_docs, other_ids
)
WITH mapped AS (
  SELECT DISTINCT person_id, doc, ndigits, src_id
  FROM (
    SELECT
      cp.person_id,
      nullif(btrim(r.traveldoc), '') AS doc,
      length(regexp_replace(btrim(r.traveldoc), '[^0-9]', '', 'g')) AS ndigits,
      r.sirena_record_pk::text AS src_id
    FROM skyteam.sirena_records r
    JOIN stage.card_person cp
      ON cp.card_key = meta.norm_loyalty_card(
           upper(substring(r.paxadditionalinfo from 'FF#([A-Za-z]{2})')),
           substring(r.paxadditionalinfo
                     from 'FF#[A-Za-z]{2}[[:space:]]*([0-9]+)')
         )
    WHERE r.paxadditionalinfo ~ 'FF#[A-Za-z]{2}'
      AND coalesce(btrim(r.traveldoc), '') NOT IN ('', 'N/A')

    UNION

    SELECT
      pa.person_id,
      nullif(btrim(r.traveldoc), '') AS doc,
      length(regexp_replace(btrim(r.traveldoc), '[^0-9]', '', 'g')) AS ndigits,
      r.sirena_record_pk::text AS src_id
    FROM skyteam.sirena_records r
    JOIN stage.person_anchor pa
      ON pa.anchor_type = 'sirena_doc'
     AND pa.anchor_key = upper(
           regexp_replace(btrim(r.traveldoc), '[^0-9A-Za-z]', '', 'g')
         )
    WHERE coalesce(btrim(r.traveldoc), '') NOT IN ('', 'N/A')
      -- FF#-строки уже идут через card_person; иначе один passport
      -- мог бы «приклеить» чужие FF-записи к cardless-человеку
      AND NOT (coalesce(r.paxadditionalinfo, '') ~ 'FF#[A-Za-z]{2}')
  ) u
),
typed AS (
  SELECT
    person_id,
    doc,
    src_id,
    CASE
      WHEN ndigits = 10 THEN 'rf'
      WHEN ndigits = 9  THEN 'foreign'
      ELSE 'other'
    END AS doc_type
  FROM mapped
  WHERE doc IS NOT NULL
),
per_type AS (
  SELECT
    person_id,
    doc_type,
    count(DISTINCT doc)::int AS n_docs,
    string_agg(DISTINCT doc, ' | ' ORDER BY doc) AS docs,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint) AS ids
  FROM typed
  GROUP BY person_id, doc_type
),
per_person AS (
  SELECT
    person_id,
    count(DISTINCT doc)::int AS n_docs,
    string_agg(DISTINCT doc, ' | ' ORDER BY doc) AS docs,
    string_agg(src_id, ' | ' ORDER BY src_id::bigint) AS ids
  FROM typed
  GROUP BY person_id
)
SELECT
  p.person_id,
  p.n_docs,
  p.docs,
  p.ids,
  coalesce(rf.n_docs, 0),
  rf.docs,
  rf.ids,
  coalesce(fg.n_docs, 0),
  fg.docs,
  fg.ids,
  coalesce(ot.n_docs, 0),
  ot.docs,
  ot.ids
FROM per_person p
LEFT JOIN per_type rf ON rf.person_id = p.person_id AND rf.doc_type = 'rf'
LEFT JOIN per_type fg ON fg.person_id = p.person_id AND fg.doc_type = 'foreign'
LEFT JOIN per_type ot ON ot.person_id = p.person_id AND ot.doc_type = 'other'
WHERE coalesce(rf.n_docs, 0) > 1
   OR coalesce(fg.n_docs, 0) > 1
   OR coalesce(ot.n_docs, 0) > 1;
