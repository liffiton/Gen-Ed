-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

CREATE TABLE context_strings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ctx_str TEXT NOT NULL UNIQUE
);

CREATE TABLE __new_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    context_name TEXT,
    context_string_id INTEGER,
    code TEXT,
    error TEXT,
    issue TEXT NOT NULL,
    response_json TEXT,
    response_text TEXT,
    topics_json TEXT,
    helpful BOOLEAN CHECK (helpful in (0, 1)),
    helpful_emoji TEXT GENERATED ALWAYS AS (CASE helpful WHEN 1 THEN '✅' WHEN 0 THEN '❌' ELSE '' END) VIRTUAL,
    user_id INTEGER NOT NULL,
    role_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(role_id) REFERENCES roles(id),
    FOREIGN KEY(context_string_id) REFERENCES context_strings(id)
);

INSERT INTO __new_queries (id, query_time, context_name, code, error, issue, response_json, response_text, topics_json, helpful, user_id, role_id)
  SELECT
    id,
    query_time,
    language,  -- moving to context_name
    code,
    error,
    issue,
    response_json,
    response_text,
    topics_json,
    helpful,
    user_id,
    role_id
  FROM queries;

DROP TABLE queries;
ALTER TABLE __new_queries RENAME TO queries;

DROP INDEX IF EXISTS queries_by_user;
CREATE INDEX queries_by_user ON queries(user_id);
DROP INDEX IF EXISTS queries_by_role;
CREATE INDEX queries_by_role ON queries(role_id);


-- Move context configs over to new format
-- In order to retain types, indexes, etc. as defined in the main gened migration,
-- we select into a new table, delete from old table, and copy back into old table.
-- Create a temporary table for unique context names from queries
CREATE TEMPORARY TABLE tmp_unique_contexts AS
SELECT DISTINCT classes.id AS class_id, queries.context_name
FROM classes
LEFT JOIN
    (SELECT roles.class_id, queries.context_name FROM queries JOIN roles ON queries.role_id=roles.id) AS queries
    ON queries.class_id=classes.id
WHERE classes.id IN (SELECT class_id FROM contexts WHERE json_array_length(json_extract(config, '$.languages')) = 0 OR json_extract(config, '$.languages') IS NULL)
ORDER BY classes.id
;

-- Create the main temporary contexts table
CREATE TEMPORARY TABLE tmp_contexts AS
SELECT
  COALESCE(lang.value, json_extract(contexts.config, '$.default_lang'), 'Default') AS name,
  contexts.class_id,
  COALESCE(lang.key, 0) AS class_order,
  CASE
    WHEN json_extract(contexts.config, '$.avoid') IS NULL THEN '{}'
    WHEN json_extract(contexts.config, '$.avoid') = '' THEN '{}'
    ELSE json_object('avoid', json_extract(contexts.config, '$.avoid'))
  END AS config
FROM contexts
LEFT JOIN json_each(contexts.config, '$.languages') AS lang
WHERE json_array_length(json_extract(contexts.config, '$.languages')) > 0

UNION ALL

SELECT
  COALESCE(tmp_unique_contexts.context_name, 'Default') AS name,
  tmp_unique_contexts.class_id,
  0 AS class_order,
  '{}' AS config
FROM tmp_unique_contexts;

-- Clean up the first temporary table
DROP TABLE tmp_unique_contexts;

DELETE FROM contexts;

INSERT INTO contexts (name, class_id, class_order, available, config)
  SELECT name, class_id, class_order, '0001-01-01', config 
  FROM tmp_contexts
  ORDER BY class_id, class_order;

-- Clean up the second temporary table
DROP TABLE tmp_contexts;

COMMIT;

VACUUM;
