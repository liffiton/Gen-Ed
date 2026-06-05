-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

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
