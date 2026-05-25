-- SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

ALTER TABLE classes_user RENAME COLUMN link_ident TO link_key;

UPDATE classes_user SET link_key = 'v1.' || link_key;

COMMIT;

PRAGMA foreign_keys = ON;
