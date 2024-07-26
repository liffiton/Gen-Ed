-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

-- Somewhat dangerous hack to switch column types given no ALTER COLUMN ability in SQLite
-- But the alternative is recreate, copy, and drop every table, keeping track of indexes, etc.
PRAGMA writable_schema = 1;
UPDATE SQLITE_MASTER SET SQL = REPLACE(SQL, ' TIMESTAMP ', ' DATETIME ');
PRAGMA writable_schema = 0;

COMMIT;

PRAGMA foreign_keys = ON;
