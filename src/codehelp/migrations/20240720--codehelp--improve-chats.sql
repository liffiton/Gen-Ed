-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

-- Rename tutor_chats -> chats and improve context storage.

CREATE TABLE chats (
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

INSERT INTO chats (id, topic, context_name, chat_json, user_id, role_id)
  SELECT
    id,
    topic,
    context,
    chat_json,
    user_id,
    role_id
  FROM tutor_chats;

DROP TABLE tutor_chats;

DROP INDEX IF EXISTS tutor_chats_by_user;
CREATE INDEX chats_by_user ON chats(user_id);
DROP INDEX IF EXISTS tutor_chats_by_role;
CREATE INDEX chats_by_role ON chats(role_id);

COMMIT;

VACUUM;
