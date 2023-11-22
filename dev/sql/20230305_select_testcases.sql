.mode csv
.headers on

SELECT *, MIN(query_time) FROM queries WHERE query_time > date("2023-09-30") AND id % 50 = 0
  GROUP BY IIF(code != "", SUBSTR(code, 0, 5), SUBSTR(issue, 5, 5))
  ORDER BY id;
