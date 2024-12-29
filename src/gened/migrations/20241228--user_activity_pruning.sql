-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE users ADD COLUMN 
    delete_status TEXT CHECK (delete_status IN ('', 'deleted', 'whitelisted')) DEFAULT '';

-- Catch any previously-deleted users
UPDATE users SET delete_status='deleted' WHERE display_name='[deleted]';

CREATE VIEW user_activity AS
SELECT
    users.id,
    users.display_name,
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
WHERE NOT users.is_admin
  AND users.id != -1
  AND users.delete_status != 'deleted'
;

COMMIT;
