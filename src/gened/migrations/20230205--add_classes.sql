-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;
    
CREATE TABLE classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lti_consumer      TEXT NOT NULL,
    lti_context_id    TEXT NOT NULL,
    lti_context_label TEXT NOT NULL,  -- name of the class
    config            TEXT NOT NULL DEFAULT "{}"  -- JSON containing class config options
);

-- Create a class for the one class we have in the roles table so far.
INSERT INTO classes (lti_consumer, lti_context_id, lti_context_label, config)
    SELECT "courses.iwu.edu", 60041, lti_context, "{}" FROM roles LIMIT 1;   -- dev
    --SELECT "courses.iwu.edu", 60891, lti_context, "{}" FROM roles LIMIT 1;   -- prod

CREATE TABLE new_roles (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    role     TEXT NOT NULL CHECK( role IN ('instructor', 'student') ),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(class_id) REFERENCES classes(id)
);

INSERT INTO new_roles SELECT id, user_id, 1, role FROM roles;

DROP TABLE roles;

ALTER TABLE new_roles RENAME TO roles;

COMMIT;
