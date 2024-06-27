-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

-- Move context configs over to new format
-- [let's not do this too often...]
UPDATE contexts
SET config = newtbl.newconfig 
FROM (
    SELECT
        contexts.id,
        json_remove(
            json_set(
                contexts.config,
                '$.languages',
                COALESCE(
                    group_concat(atom, char(10)),
                    json_extract(contexts.config, '$.default_lang')
                )
            ),
            '$.default_lang'
        ) AS newconfig
    FROM
        contexts
        LEFT JOIN json_each(json_extract(contexts.config, '$.languages'))
    GROUP BY contexts.id
) AS newtbl
WHERE newtbl.id=contexts.id;

COMMIT;
