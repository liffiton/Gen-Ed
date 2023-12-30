-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

CREATE TABLE __new_users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,  -- ideally email
    password TEXT,  -- could be null if registered via LTI
    is_admin BOOLEAN NOT NULL CHECK (is_admin IN (0,1)) DEFAULT 0,
    is_tester BOOLEAN NOT NULL CHECK (is_tester IN (0,1)) DEFAULT 0,
    lti_id   TEXT UNIQUE,  -- combination of LTI consumer, LTI userid, and email -- used to connect LTI sessions to users
    lti_consumer_id INTEGER,  -- the LTI consumer that registered this user, if applicable
    query_tokens INTEGER DEFAULT 0,  -- number of tokens left for making queries - NULL means no limit, non-NULL for SSO/demo users, 0 means cut off
    created  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(lti_consumer_id) REFERENCES consumers(id)
);

INSERT INTO __new_users (id, username, password, is_admin, is_tester, lti_id, lti_consumer_id, query_tokens, created)
    SELECT
        users.id,
        users.username,
        users.password,
        users.is_admin,
        users.is_tester,
        users.lti_id,
        consumers.id,
        users.query_tokens,
        users.created
    FROM users
    LEFT JOIN consumers ON users.lti_consumer = consumers.lti_consumer;

DROP TABLE users;
ALTER TABLE __new_users RENAME TO users;


CREATE TABLE __new_classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lti_consumer_id   INTEGER NOT NULL,  -- references consumers.id
    lti_context_id    TEXT NOT NULL,  -- used for matching LTI requests to rows in this table
    lti_context_label TEXT NOT NULL,  -- name of the class
    config            TEXT NOT NULL DEFAULT "{}",  -- JSON containing class config options
    created           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(lti_consumer_id) REFERENCES consumers(id)
);

INSERT INTO __new_classes (id, lti_consumer_id, lti_context_id, lti_context_label, config, created)
    SELECT
        classes.id,
        consumers.id,
        classes.lti_context_id,
        classes.lti_context_label,
        classes.config,
        classes.created
    FROM classes
    LEFT JOIN consumers ON classes.lti_consumer = consumers.lti_consumer;

DROP TABLE classes;
ALTER TABLE __new_classes RENAME TO classes;


COMMIT;
