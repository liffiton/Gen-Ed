-- SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

-- Unify contexts and tutors into a shared config_items table
-- CREATE TABLE IF NOT EXISTS ensures this works whether old tables exist or not

PRAGMA foreign_keys = OFF;

BEGIN;

CREATE TABLE IF NOT EXISTS config_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id    INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    item_type   TEXT NOT NULL,
    name        TEXT NOT NULL,
    class_order INTEGER NOT NULL,
    available   DATE NOT NULL,
    config      TEXT NOT NULL DEFAULT '{}',
    created     DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS config_items_by_class_type_name ON config_items(class_id, item_type, name);

-- Stub tables so INSERT...SELECT always compiles
-- On existing DBs: no-op (real tables already exist with data)
-- On new/partial DBs: empty tables yield 0 rows
CREATE TABLE IF NOT EXISTS contexts (
    class_id    INTEGER NOT NULL,
    name        TEXT NOT NULL,
    class_order INTEGER NOT NULL,
    available   DATE NOT NULL,
    config      TEXT NOT NULL DEFAULT '{}',
    created     DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tutors (
    class_id    INTEGER NOT NULL,
    name        TEXT NOT NULL,
    class_order INTEGER NOT NULL,
    available   DATE NOT NULL,
    config      TEXT NOT NULL DEFAULT '{}',
    created     DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO config_items (class_id, item_type, name, class_order, available, config, created)
SELECT class_id, 'context', name, class_order, available, config, created
FROM contexts;

INSERT INTO config_items (class_id, item_type, name, class_order, available, config, created)
SELECT class_id, 'guided_tutor', name, class_order, available, config, created
FROM tutors;

DROP TABLE IF EXISTS contexts;
DROP TABLE IF EXISTS tutors;

COMMIT;

PRAGMA foreign_keys = ON;
