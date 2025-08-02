-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

-- Contexts for use in a class
-- Config stored as JSON for flexibility, esp. during development
DROP TABLE IF EXISTS contexts;
CREATE TABLE contexts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    class_id    INTEGER NOT NULL,
    class_order INTEGER NOT NULL,  -- position within manual ordering of contexts within a class
    available   DATE NOT NULL,  -- date on which this context will be available to students (& mindate=available, maxdate=disabled)
    config      TEXT NOT NULL DEFAULT "{}",  -- JSON containing context config options
    created     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id)
);
-- names must be unique within a class, and we often look up by class and name
DROP INDEX IF EXISTS contexts_by_class_name;
CREATE UNIQUE INDEX  contexts_by_class_name ON contexts(class_id, name);

DROP TABLE IF EXISTS context_strings;
CREATE TABLE context_strings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ctx_str TEXT NOT NULL UNIQUE
);
