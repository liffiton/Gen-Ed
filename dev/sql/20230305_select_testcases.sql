SELECT *, MIN(query_time) FROM queries WHERE language="python" AND query_time > "2023-01-30" AND id % 6 = 0
  GROUP BY IIF(code != "", SUBSTR(code, 0, 5), SUBSTR(issue, 5, 5))
  ORDER BY id;