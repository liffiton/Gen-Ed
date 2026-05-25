-- SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

ALTER TABLE code_queries DROP COLUMN topics_json;

COMMIT;

PRAGMA foreign_keys = ON;
