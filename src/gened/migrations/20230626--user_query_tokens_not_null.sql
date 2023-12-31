-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;
BEGIN;

CREATE TABLE __new_users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    auth_provider INTEGER NOT NULL,
    full_name     TEXT,
    email         TEXT,
    auth_name     TEXT,
    display_name  TEXT GENERATED ALWAYS AS (COALESCE(full_name, email, auth_name)) VIRTUAL NOT NULL,  -- NOT NULL on COALESCE effectively requires one of full_name, email, and auth_name
    is_admin      BOOLEAN NOT NULL CHECK (is_admin IN (0,1)) DEFAULT 0,
    is_tester     BOOLEAN NOT NULL CHECK (is_tester IN (0,1)) DEFAULT 0,
    query_tokens  INTEGER NOT NULL DEFAULT 0,  -- number of tokens left for making queries - 0 means cut off
    created       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(auth_provider) REFERENCES auth_providers(id)
);

INSERT INTO __new_users (id, auth_provider, full_name, email, auth_name, is_admin, is_tester, query_tokens, created)
    SELECT
        users.id,
        users.auth_provider,
        users.full_name,
        users.email,
        users.auth_name,
        users.is_admin,
        users.is_tester,
        IIF (users.query_tokens IS NULL, 0, users.query_tokens),
        users.created
    FROM users;

DROP TABLE users;
ALTER TABLE __new_users RENAME TO users;


COMMIT;
PRAGMA foreign_keys = ON;
