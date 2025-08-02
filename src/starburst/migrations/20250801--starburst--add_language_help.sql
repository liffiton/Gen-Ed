-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

CREATE TABLE language_help_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    writing TEXT,
    response_json TEXT,
    response_text TEXT,
    user_id INTEGER NOT NULL,
    role_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(role_id) REFERENCES roles(id)
);

-- And create the indexes while we're at it
DROP INDEX IF EXISTS queries_by_user;
CREATE INDEX language_help_queries_by_user ON language_help_queries(user_id);
DROP INDEX IF EXISTS queries_by_role;
CREATE INDEX language_help_queries_by_role ON language_help_queries(role_id);

COMMIT;
