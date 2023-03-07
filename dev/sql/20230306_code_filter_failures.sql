-- New
SELECT
    SUM(json_extract(response_json, '$[1].choices[0].message.content') LIKE "%```%"),
    SUM(json_extract(response_json, '$[2].choices[0].message.content') LIKE "%```%") 
	FROM queries WHERE id >= 935 ;  -- 149 and 49

-- Old
SELECT
    SUM(response_json LIKE "%```%"),
    SUM(response_text LIKE "%```%") 
	FROM queries WHERE id < 935 ;  -- 546 and 54

-- Extract examples w/ code still in
SELECT
    json_extract(response_json, '$[1].choices[0].message.content')
	FROM queries
	WHERE id >= 935 AND
          json_extract(response_json, '$[2].choices[0].message.content') LIKE "%```%"
	;
