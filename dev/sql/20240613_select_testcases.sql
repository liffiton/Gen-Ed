.mode csv
.headers on

SELECT queries.id, queries.query_time, queries.language, queries.code, queries.error, queries.issue, json_extract(queries.response_text, '$.main') as main_response, json_extract(queries.response_text, '$.insufficient') as insufficient_response
  FROM queries
  JOIN roles ON queries.role_id = roles.id
  WHERE query_time > date("2023-09-30")  -- only once it was in use in real classes
    AND roles.role = "student"  -- only queries from students in a class
  ORDER BY RANDOM()
  LIMIT 100;
