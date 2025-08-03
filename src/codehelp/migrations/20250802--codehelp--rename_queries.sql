-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE queries RENAME TO code_queries;

-- And create the indexes while we're at it
DROP INDEX IF EXISTS queries_by_user;
CREATE INDEX code_queries_by_user ON code_queries(user_id);
DROP INDEX IF EXISTS queries_by_role;
CREATE INDEX code_queries_by_role ON code_queries(role_id);

COMMIT;
