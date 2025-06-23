-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

CREATE TABLE tutors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id    INTEGER NOT NULL,
    config      TEXT NOT NULL DEFAULT "{}",  -- JSON containing tutor configuration
    FOREIGN KEY(class_id) REFERENCES classes(id)
);

COMMIT;

VACUUM;
