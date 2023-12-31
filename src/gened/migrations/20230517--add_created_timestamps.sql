-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;
BEGIN;

-- Can't add a column w/ non-constant default, so need to recreate tables
-- and copy data into them...

DROP TABLE IF EXISTS __old_consumers;
ALTER TABLE consumers RENAME TO __old_consumers;
CREATE TABLE consumers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lti_consumer  TEXT NOT NULL UNIQUE,
    lti_secret    TEXT,
    openai_key    TEXT,
    created       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO consumers SELECT *, NULL AS created FROM __old_consumers;
DROP TABLE __old_consumers;
CREATE UNIQUE INDEX consumers_idx ON consumers(lti_consumer);

---

DROP TABLE IF EXISTS __old_users;
ALTER TABLE users RENAME TO __old_users;
CREATE TABLE users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,  -- ideally email
    password TEXT,  -- could be null if registered via LTI
    is_admin BOOLEAN NOT NULL CHECK (is_admin IN (0,1)) DEFAULT 0,
    lti_id   TEXT UNIQUE,  -- combination of LTI consumer, LTI userid, and email -- used to connect LTI sessions to users
    lti_consumer TEXT,  -- the LTI consumer that registered this user, if applicable
    query_tokens INTEGER,  -- number of tokens left for making queries - for demo users - default NULL means no limit
    created  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO users SELECT *, NULL AS created FROM __old_users;
DROP TABLE __old_users;
CREATE UNIQUE INDEX unique_username_without_lti ON users (username) WHERE lti_id IS NULL;

---

DROP TABLE IF EXISTS __old_classes;
ALTER TABLE classes RENAME TO __old_classes;
CREATE TABLE classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lti_consumer      TEXT NOT NULL,
    lti_context_id    TEXT NOT NULL,
    lti_context_label TEXT NOT NULL,  -- name of the class
    config            TEXT NOT NULL DEFAULT "{}",  -- JSON containing class config options
    created           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO classes SELECT *, NULL AS created FROM __old_classes;
DROP TABLE __old_classes;

---

COMMIT;
PRAGMA foreign_keys = ON;
