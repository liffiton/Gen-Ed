-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

-- NOTE: This deletes all existing chats.  It's an experimental feature, and it's not worth retaining old ones.
DROP INDEX IF EXISTS chats_by_user;
DROP INDEX IF EXISTS chats_by_role;
DROP TABLE chats;

CREATE TABLE chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_started DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    chat_json TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    role_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(role_id) REFERENCES roles(id)
);
CREATE INDEX chats_by_user ON chats(user_id);
CREATE INDEX chats_by_role ON chats(role_id);


COMMIT;

VACUUM;
