-- SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

-- Transform old context configs into the role-based shape:
--   {"name": ..., "details": ..., "guidance": ..., "avoid": ...}
--
-- Old configs store environment/tools separately from details.  Fold the
-- newline-separated tools list into details as a single "; "-joined line,
-- keeping all other content as-is.  Anonymized rows written by class deletion
-- (config '{}' with a "[deleted]" name) are intentionally left untouched.

BEGIN;

WITH old_contexts AS MATERIALIZED (
    SELECT
        id,
        name AS column_name,
        config AS old_config,
        trim(
            replace(
                replace(COALESCE(json_extract(config, '$.tools'), ''), char(13, 10), char(10)),
                char(13),
                char(10)
            ),
            ' ' || char(9) || char(10) || char(13)
        ) AS old_tools,
        trim(
            replace(
                replace(COALESCE(json_extract(config, '$.details'), ''), char(13, 10), char(10)),
                char(13),
                char(10)
            ),
            ' ' || char(9) || char(10) || char(13)
        ) AS old_details
    FROM config_items
    WHERE item_type = 'context'
      AND NOT (config = '{}' AND name LIKE '[deleted]%')
)
UPDATE config_items
SET config = json_remove(
    json_set(
        old_config,
        '$.name', COALESCE(json_extract(old_config, '$.name'), column_name),
        '$.details', CASE
            WHEN old_tools = '' AND old_details = '' THEN ''
            WHEN old_tools = '' THEN old_details
            WHEN old_details = '' THEN
                '**Environment and tools:** ' || replace(old_tools, char(10), '; ')
            ELSE
                '**Environment and tools:** ' || replace(old_tools, char(10), '; ')
                || char(10) || char(10) || old_details
        END,
        '$.guidance', COALESCE(json_extract(old_config, '$.guidance'), ''),
        '$.avoid', COALESCE(json_extract(old_config, '$.avoid'), '')
    ),
    '$.tools'
)
FROM old_contexts
WHERE old_contexts.id = config_items.id;

COMMIT;
