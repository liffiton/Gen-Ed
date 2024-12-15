-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS queries;

CREATE TABLE queries (
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
