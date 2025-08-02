-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

DROP TABLE IF EXISTS queries;
CREATE TABLE queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    context_name TEXT,
    context_string_id INTEGER,
    code TEXT,
    error TEXT,
    issue TEXT NOT NULL,
    response_json TEXT,
    response_text TEXT,
    topics_json TEXT,
    helpful BOOLEAN CHECK (helpful in (0, 1)),
    helpful_emoji TEXT GENERATED ALWAYS AS (CASE helpful WHEN 1 THEN '✅' WHEN 0 THEN '❌' ELSE '' END) VIRTUAL,
    user_id INTEGER NOT NULL,
    role_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(role_id) REFERENCES roles(id),
    FOREIGN KEY(context_string_id) REFERENCES context_strings(id)
);
DROP INDEX IF EXISTS queries_by_user;
CREATE INDEX queries_by_user ON queries(user_id);
DROP INDEX IF EXISTS queries_by_role;
CREATE INDEX queries_by_role ON queries(role_id);
