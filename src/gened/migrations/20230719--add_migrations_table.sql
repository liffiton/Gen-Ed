-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

-- Track which migrations have been applied to this database
CREATE TABLE migrations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL UNIQUE,
    applied_on  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    skipped     BOOLEAN NOT NULL CHECK (skipped IN (0,1)) DEFAULT 0,
    succeeded   BOOLEAN NOT NULL CHECK (skipped IN (0,1)) DEFAULT 0
);

COMMIT;

PRAGMA foreign_keys = ON;
