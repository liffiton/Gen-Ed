-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE chats RENAME TO __old_chats;

CREATE TABLE chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_started DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    topic TEXT NOT NULL,
    context_name TEXT,
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

INSERT INTO chats (id, chat_started, topic, context_name, chat_json, user_id, role_id)
  SELECT id, chat_started, topic, context_name, chat_json, user_id, role_id FROM __old_chats;

DROP TABLE __old_chats;

COMMIT;

VACUUM;
