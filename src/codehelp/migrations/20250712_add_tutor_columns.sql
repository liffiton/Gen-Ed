-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

-- Make the new columns NOT NULL after populating them
-- SQLite doesn't support ALTER COLUMN, so we need to recreate the table
CREATE TABLE __new_tutors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    class_id    INTEGER NOT NULL,
    class_order INTEGER NOT NULL,  -- position within manual ordering of tutors within a class
    available   DATE NOT NULL,  -- date on which this tutor will be available to students (& mindate=available, maxdate=disabled)
    config      TEXT NOT NULL DEFAULT "{}",  -- JSON containing tutor configuration
    created     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id)
);

-- Copy data from old table to new table
INSERT INTO __new_tutors (id, name, class_id, class_order, available, config, created)
SELECT
    id,
    COALESCE(json_extract(config, '$.topic'), 'Unnamed Tutor'),
    class_id,
    0,
    '9999-12-31',
    config,
    CURRENT_TIMESTAMP
FROM tutors;

-- Drop old table and rename new table
DROP TABLE tutors;
ALTER TABLE __new_tutors RENAME TO tutors;

-- Add index: names must be unique within a class
DROP INDEX IF EXISTS tutors_by_class_name;
CREATE UNIQUE INDEX  tutors_by_class_name ON tutors(class_id, name);

COMMIT;

VACUUM;
