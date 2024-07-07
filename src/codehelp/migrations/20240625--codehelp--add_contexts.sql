-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE queries ADD COLUMN context_name TEXT;
ALTER TABLE queries ADD COLUMN context TEXT;
UPDATE queries SET context_name=language;
UPDATE queries SET context=language;
ALTER TABLE queries DROP COLUMN language;

-- Move context configs over to new format
-- In order to retain types, indexes, etc. as defined in the main gened migration,
-- we select into a new table, delete from old table, and copy back into old table.
CREATE TABLE tmp_contexts AS
SELECT
  COALESCE(lang.value, json_extract(contexts.config, '$.default_lang'), 'Default') AS name,
  class_id,
  COALESCE(lang.key, 0) AS class_order,
  CASE
    WHEN json_extract(contexts.config, '$.avoid') IS NULL THEN '{}'
    WHEN json_extract(contexts.config, '$.avoid') = '' THEN '{}'
    ELSE json_object('avoid', json_extract(contexts.config, '$.avoid'))
	END
	AS config
FROM contexts
LEFT JOIN json_each(contexts.config, '$.languages') AS lang;

DELETE FROM contexts;

INSERT INTO contexts (name, class_id, class_order, available, config)
  SELECT name, class_id, class_order, '0001-01-01', config FROM tmp_contexts;

DROP TABLE tmp_contexts;

COMMIT;

VACUUM;
