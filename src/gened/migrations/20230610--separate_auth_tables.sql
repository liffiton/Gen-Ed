-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

DROP INDEX IF EXISTS unique_username_without_lti;


CREATE TABLE auth_providers (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT NOT NULL
);
INSERT INTO auth_providers(name) VALUES
    ('local'),
    ('lti'),
    ('demo'),
    ('google'),
    ('github');


CREATE TABLE __new_users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    auth_provider INTEGER NOT NULL,
    full_name     TEXT,
    email         TEXT,
    auth_name     TEXT,
    display_name  TEXT GENERATED ALWAYS AS (COALESCE(full_name, email, auth_name)) VIRTUAL NOT NULL,  -- NOT NULL on COALESCE effectively requires one of full_name, email, and auth_name
    is_admin      BOOLEAN NOT NULL CHECK (is_admin IN (0,1)) DEFAULT 0,
    is_tester     BOOLEAN NOT NULL CHECK (is_tester IN (0,1)) DEFAULT 0,
    query_tokens  INTEGER DEFAULT 0,  -- number of tokens left for making queries - NULL means no limit, non-NULL for SSO/demo users, 0 means cut off
    created       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(auth_provider) REFERENCES auth_providers(id)
);

-- local users
INSERT INTO __new_users (id, auth_provider, auth_name, is_admin, is_tester, query_tokens, created)
    SELECT
        id,
        1,  -- local
        username,
        is_admin,
        is_tester,
        query_tokens,
        created
    FROM users
    WHERE PASSWORD IS NOT NULL;

-- LTI users
INSERT INTO __new_users (id, auth_provider, email, is_admin, is_tester, query_tokens, created)
    SELECT
        id,
        2,  -- LTI
        username,
        is_admin,
        is_tester,
        query_tokens,
        created
    FROM users
    WHERE lti_id IS NOT NULL;

-- demo users
INSERT INTO __new_users (id, auth_provider, auth_name, is_admin, is_tester, query_tokens, created)
    SELECT
        id,
        3,  -- demo
        username,
        is_admin,
        is_tester,
        query_tokens,
        created
    FROM users
    WHERE username LIKE "demo%";



CREATE TABLE auth_local (
    user_id       INTEGER PRIMARY KEY,
    username      TEXT NOT NULL,
    password      TEXT NOT NULL,
    created       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

INSERT INTO auth_local(user_id, username, password, created)
    SELECT id, username, password, created FROM users WHERE password IS NOT NULL;


    
CREATE TABLE auth_external (
    user_id       INTEGER PRIMARY KEY,
    auth_provider INTEGER NOT NULL,
    ext_id        TEXT NOT NULL,  -- the primary, unique ID used by the external provider
    created       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(auth_provider) REFERENCES auth_providers(id)
);
DROP INDEX IF EXISTS auth_external_by_ext_id;
CREATE UNIQUE INDEX auth_external_by_ext_id ON auth_external(auth_provider, ext_id);

INSERT INTO auth_external(user_id, auth_provider, ext_id, created)
    SELECT id, 2, lti_id, created FROM users WHERE lti_id IS NOT NULL;
             --2 = LTI auth provider



DROP TABLE users;
ALTER TABLE __new_users RENAME TO users;


COMMIT;

PRAGMA foreign_keys = ON;
