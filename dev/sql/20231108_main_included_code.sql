.mode csv
.headers on

SELECT *, json_extract(response_json, "$[0].choices[0].message.content") AS response_text  -- get the data the cleanup prompt actually uses
FROM queries
WHERE
    id % 15 = 0
    AND (
    0
    OR json_extract(response_json, "$[0].choices[0].message") LIKE "%```%"
    OR json_extract(response_json, "$[0].choices[1].message") LIKE "%```%"
    OR json_extract(response_json, "$[0].choices[0].message") LIKE "%look like%"
    OR json_extract(response_json, "$[0].choices[1].message") LIKE "%look like%"
    )
ORDER BY queries.id DESC
LIMIT 50
