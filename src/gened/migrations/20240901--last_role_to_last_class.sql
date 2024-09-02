-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

CREATE UNIQUE INDEX  roles_user_class_unique ON roles(user_id, class_id);

ALTER TABLE users ADD COLUMN 
    last_class_id INTEGER;  -- most recently active class, used to re-activate on login (note: user may no longer have active role in this class)

UPDATE users
SET last_class_id = (
    SELECT class_id
    FROM roles
    WHERE roles.id=users.last_role_id
)
WHERE last_role_id IS NOT NULL;

ALTER TABLE users DROP COLUMN last_role_id;

COMMIT;
