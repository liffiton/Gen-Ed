-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS queries;

CREATE TABLE queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    assignment TEXT,
    topics TEXT,
    response_json TEXT,
    response_text TEXT,
    helpful BOOLEAN CHECK (helpful in (0, 1)),
    helpful_emoji TEXT GENERATED ALWAYS AS (CASE helpful WHEN 1 THEN '✅' WHEN 0 THEN '❌' ELSE '' END) VIRTUAL,
    user_id INTEGER NOT NULL,
    role_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(role_id) REFERENCES roles(id)
);
