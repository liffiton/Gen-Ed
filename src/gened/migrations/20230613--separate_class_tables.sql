-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

-- Classes and their config
-- (superset type for classes_lti and classes_user)
-- Config stored as JSON for flexibility, esp. during development
CREATE TABLE __new_classes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    enabled  BOOLEAN NOT NULL CHECK (enabled IN (0,1)) DEFAULT 1,
    config   TEXT NOT NULL DEFAULT "{}",  -- JSON containing class config options
    created  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Classes created/accessed via LTI
CREATE TABLE classes_lti (
    class_id          INTEGER PRIMARY KEY,  -- references classes.id
    lti_consumer_id   INTEGER NOT NULL,  -- references consumers.id
    lti_context_id    TEXT NOT NULL,  -- class ID from the LMS
    created           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id),
    FOREIGN KEY(lti_consumer_id) REFERENCES consumers(id)
);
DROP INDEX IF EXISTS classes_lti_by_consumer_context;
CREATE UNIQUE INDEX  classes_lti_by_consumer_context ON classes_lti(lti_consumer_id, lti_context_id);

-- Classes created by a user, accessed via class link
CREATE TABLE classes_user (
    class_id         INTEGER PRIMARY KEY,  -- references classes.id
    openai_key       TEXT,
    link_ident       TEXT NOT NULL UNIQUE,  -- random (unguessable) identifier used in access/registration link for this class
    creator_user_id  INTEGER NOT NULL,  -- references users.id
    created          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id),
    FOREIGN KEY(creator_user_id) REFERENCES users(id)
);
DROP INDEX IF EXISTS classes_user_by_link_ident;
CREATE UNIQUE INDEX  classes_user_by_link_ident ON classes_user(link_ident);




-- shift data

INSERT INTO classes_lti (class_id, lti_consumer_id, lti_context_id, created)
    SELECT
        id,
        lti_consumer_id,
        lti_context_id,
        created
    FROM classes;

INSERT INTO __new_classes (id, name, config, created)
    SELECT
        id,
        lti_context_label,
        config,
        created
    FROM classes;


-- overwrite table

DROP TABLE classes;
ALTER TABLE __new_classes RENAME TO classes;


COMMIT;

PRAGMA foreign_keys = ON;
