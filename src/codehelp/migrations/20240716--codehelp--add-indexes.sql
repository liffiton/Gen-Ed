-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

DROP INDEX IF EXISTS queries_by_user;
CREATE INDEX queries_by_user ON queries(user_id);
DROP INDEX IF EXISTS queries_by_role;
CREATE INDEX queries_by_role ON queries(role_id);

DROP INDEX IF EXISTS tutor_chats_by_user;
CREATE INDEX tutor_chats_by_user ON tutor_chats(user_id);
DROP INDEX IF EXISTS tutor_chats_by_role;
CREATE INDEX tutor_chats_by_role ON tutor_chats(role_id);

COMMIT;
