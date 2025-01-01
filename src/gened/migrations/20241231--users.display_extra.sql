-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE users ADD COLUMN 
    display_extra TEXT GENERATED ALWAYS AS (IIF(auth_provider = 5, '@' || auth_name, email)) VIRTUAL;  -- 5=Github, use @authname; else use email (okay if null)

DROP VIEW IF EXISTS user_activity;
CREATE VIEW user_activity AS
SELECT
    users.id,
    users.display_name,
    users.display_extra,
    auth_providers.name AS auth_provider,
    users.delete_status,
    users.created,
    (
        SELECT MAX(q.query_time)
        FROM queries q
        WHERE q.user_id = users.id
    ) as last_query_time,
    (
        SELECT MAX(q.query_time)
        FROM roles r_inst
        JOIN roles r_student ON r_student.class_id=r_inst.class_id
        JOIN queries q ON q.role_id=r_student.id
        WHERE r_inst.user_id = users.id
          AND r_inst.role = 'instructor'
    ) as last_instructor_query_time
FROM users
LEFT JOIN auth_providers ON auth_providers.id=users.auth_provider
WHERE NOT users.is_admin
  AND users.id != -1
  AND users.delete_status != 'deleted'
;

COMMIT;
