-- SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

ALTER TABLE demo_links ADD COLUMN
    is_instructor BOOLEAN NOT NULL CHECK (is_instructor IN (0,1)) DEFAULT 0
;

COMMIT;

PRAGMA foreign_keys = ON;
