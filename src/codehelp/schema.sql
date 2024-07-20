-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS queries;
CREATE TABLE queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
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

DROP TABLE IF EXISTS tutor_chats;
CREATE TABLE tutor_chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_started TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    topic TEXT NOT NULL,
    context_name TEXT,
    context_string_id INTEGER,
    chat_json TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    role_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(role_id) REFERENCES roles(id),
    FOREIGN KEY(context_string_id) REFERENCES context_strings(id)
);
DROP INDEX IF EXISTS tutor_chats_by_user;
CREATE INDEX tutor_chats_by_user ON tutor_chats(user_id);
DROP INDEX IF EXISTS tutor_chats_by_role;
CREATE INDEX tutor_chats_by_role ON tutor_chats(role_id);

DROP TABLE IF EXISTS context_strings;
CREATE TABLE context_strings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ctx_str TEXT NOT NULL UNIQUE
);
