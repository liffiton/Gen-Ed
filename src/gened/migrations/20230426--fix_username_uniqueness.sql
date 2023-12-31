-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

ALTER TABLE users RENAME TO __old_users;

CREATE TABLE users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,  -- ideally email
    password TEXT,  -- could be null if registered via LTI
    is_admin BOOLEAN NOT NULL CHECK (is_admin IN (0,1)) DEFAULT 0,
    lti_id   TEXT UNIQUE,  -- combination of LTI consumer, LTI userid, and email -- used to connect LTI sessions to users
    lti_consumer  TEXT  -- the LTI consumer that registered this user, if applicable
);
-- require unique usernames if no LTI ID (allows multiple users w/ same username if coming from different LTI consumers)
DROP INDEX IF EXISTS unique_username_without_lti;
CREATE UNIQUE INDEX unique_username_without_lti ON users (username) WHERE lti_id IS NULL;

INSERT INTO users SELECT * FROM __old_users;

COMMIT;

PRAGMA foreign_keys = ON;
