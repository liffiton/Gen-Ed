-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

-- Add created column to roles with default
CREATE TABLE __new_roles (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    role     TEXT NOT NULL CHECK( role IN ('instructor', 'student') ),
    active   BOOLEAN NOT NULL CHECK (active IN (0,1)) DEFAULT 1,  -- if not active, the user has no permissions in the class
    created  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(class_id) REFERENCES classes(id)
);

-- Copy data over, defaulting existing roles' datetimes to creation time of associated class
INSERT INTO __new_roles (id, user_id, class_id, role, active, created)
    SELECT
        roles.id,
        roles.user_id,
        roles.class_id,
        roles.role,
        roles.active,
        classes.created
    FROM roles
    LEFT JOIN classes ON classes.id=roles.class_id
;

-- overwrite table
-- (need to drop the view that was created automatically because it relies on roles, but it will be created automatically at startup every time)
DROP VIEW v_user_activity;
DROP TABLE roles;
ALTER TABLE __new_roles RENAME TO roles;

-- Update the indexes
DROP INDEX IF EXISTS roles_user_class_unique;
CREATE UNIQUE INDEX  roles_user_class_unique ON roles(user_id, class_id) WHERE user_id != -1;  -- not unique for deleted users
DROP INDEX IF EXISTS roles_by_class_id;
CREATE INDEX roles_by_class_id ON roles(class_id);


COMMIT;

PRAGMA foreign_keys = ON;
