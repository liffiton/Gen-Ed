.mode box
SELECT
	AVG(Prompt) AS Prompt_avg,
	AVG(Completion) AS Completion_avg
	FROM (
		SELECT
            q.id,
            SUM(json_extract(value, '$.usage.prompt_tokens')) AS "Prompt", 
            SUM(json_extract(value, '$.usage.completion_tokens')) AS "Completion"
        FROM queries AS q, json_each(q.response_json, '$')
        WHERE json_valid(value)
        GROUP BY q.id
        ORDER BY q.id DESC
        LIMIT 10000
	)
