-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

DROP TABLE IF EXISTS chats;
CREATE TABLE chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_started DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    chat_json TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    role_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(role_id) REFERENCES roles(id)
);
DROP INDEX IF EXISTS chats_by_user;
CREATE INDEX chats_by_user ON chats(user_id);
DROP INDEX IF EXISTS chats_by_role;
CREATE INDEX chats_by_role ON chats(role_id);

-- Focused tutors for use in a class
-- Config stored as JSON for flexibility, esp. during development
DROP TABLE IF EXISTS tutors;
CREATE TABLE tutors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    class_id    INTEGER NOT NULL,
    class_order INTEGER NOT NULL,  -- position within manual ordering of tutors within a class
    available   DATE NOT NULL,  -- date on which this tutor will be available to students (& mindate=available, maxdate=disabled)
    config      TEXT NOT NULL DEFAULT "{}",  -- JSON containing tutor configuration
    created     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id)
);
-- names must be unique within a class
DROP INDEX IF EXISTS tutors_by_class_name;
CREATE UNIQUE INDEX  tutors_by_class_name ON tutors(class_id, name);

COMMIT;
