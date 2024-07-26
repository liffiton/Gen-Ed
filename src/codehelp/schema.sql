-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = ON;

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

DROP TABLE IF EXISTS chats;
CREATE TABLE chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_started DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
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
DROP INDEX IF EXISTS chats_by_user;
CREATE INDEX chats_by_user ON chats(user_id);
DROP INDEX IF EXISTS chats_by_role;
CREATE INDEX chats_by_role ON chats(role_id);

-- Contexts for use in a class
-- Config stored as JSON for flexibility, esp. during development
DROP TABLE IF EXISTS contexts;
CREATE TABLE contexts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    class_id    INTEGER NOT NULL,
    class_order INTEGER NOT NULL,  -- position within manual ordering of contexts within a class
    available   DATE NOT NULL,  -- date on which this context will be available to students (& mindate=available, maxdate=disabled)
    config      TEXT NOT NULL DEFAULT "{}",  -- JSON containing context config options
    created     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id)
);
-- names must be unique within a class, and we often look up by class and name
DROP INDEX IF EXISTS contexts_by_class_name;
CREATE UNIQUE INDEX  contexts_by_class_name ON contexts(class_id, name);

DROP TABLE IF EXISTS context_strings;
CREATE TABLE context_strings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ctx_str TEXT NOT NULL UNIQUE
);
