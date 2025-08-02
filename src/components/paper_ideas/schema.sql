-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

DROP TABLE IF EXISTS paper_ideas_queries;

CREATE TABLE paper_ideas_queries (
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

DROP INDEX IF EXISTS paper_ideas_queries_by_user;
CREATE INDEX paper_ideas_queries_by_user ON paper_ideas_queries(user_id);
DROP INDEX IF EXISTS paper_ideas_queries_by_role;
CREATE INDEX paper_ideas_queries_by_role ON paper_ideas_queries(role_id);
