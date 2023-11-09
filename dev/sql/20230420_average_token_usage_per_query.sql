SELECT
	AVG(Prompt),
	AVG(Completion)
	FROM (
		SELECT
		   queries.id,
		   SUM(json_extract(value, '$.usage.prompt_tokens')) AS "Prompt", 
		   SUM(json_extract(value, '$.usage.completion_tokens')) AS "Completion"
		 FROM queries, json_each(queries.response_json, '$')
		 WHERE queries.response_json LIKE "[{%"
         AND queries.response_json NOT LIKE "%""]"  -- filter out lists w/ an error message at the end
		 GROUP BY queries.id
		 ORDER BY queries.id DESC
		 LIMIT 2500
	)
