-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

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
        FROM queries q
        WHERE q.role_id IN (
            SELECT r_student.id
            FROM roles r_student
            JOIN roles r_inst ON r_student.class_id=r_inst.class_id
            WHERE r_inst.user_id = users.id
              AND r_inst.role = 'instructor'
        )
    ) as last_instructor_query_time
FROM users
LEFT JOIN auth_providers ON auth_providers.id=users.auth_provider
WHERE NOT users.is_admin
  AND users.id != -1
  AND users.delete_status != 'deleted'
;

CREATE INDEX roles_by_class_id ON roles(class_id);

COMMIT;

PRAGMA foreign_keys = ON;
