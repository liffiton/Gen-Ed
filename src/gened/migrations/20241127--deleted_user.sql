-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

-- user row to link for deleted roles
INSERT INTO users (id, auth_provider, full_name) VALUES (-1, 1, '[deleted]');

-- reset unique roles index to exclude deleted users
DROP INDEX IF EXISTS roles_user_class_unique;
CREATE UNIQUE INDEX  roles_user_class_unique ON roles(user_id, class_id) WHERE user_id != -1;  -- not unique for deleted users

COMMIT;
