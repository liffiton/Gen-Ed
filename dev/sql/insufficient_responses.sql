.mode csv
.headers on
SELECT
  id, language, code, error, issue, json_extract(response_text, '$.insufficient') as insufficient_response
  FROM queries
  WHERE insufficient_response IS NOT NULL
  ORDER BY id DESC   -- the latest ones, to get the most recent prompt and model behavior
  LIMIT 100          -- just a reasonable number of them
;
