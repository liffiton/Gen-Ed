-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;


-- Recreate roles table to drop old/incorrect foreign key references caused by previous table renames

CREATE TABLE __new_roles (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    role     TEXT NOT NULL CHECK( role IN ('instructor', 'student') ),
    active   BOOLEAN NOT NULL CHECK (active IN (0,1)) DEFAULT 1,  -- if not active, the user has no permissions in the class
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(class_id) REFERENCES classes(id)
);

INSERT INTO __new_roles (id, user_id, class_id, role, active)
  SELECT id, user_id, class_id, role, active FROM roles;

-- overwrite table
PRAGMA legacy_alter_table = ON;  -- so dropping the table doesn't fail due to attached views, etc.
DROP TABLE roles;
ALTER TABLE __new_roles RENAME TO roles;
PRAGMA legacy_alter_table = OFF; -- back to normal

-- recreate index
DROP INDEX IF EXISTS roles_user_class_unique;
CREATE UNIQUE INDEX  roles_user_class_unique ON roles(user_id, class_id) WHERE user_id != -1;  -- not unique for deleted users


COMMIT;

PRAGMA foreign_keys = ON;
