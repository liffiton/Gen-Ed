-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

-- Contexts for use in a class
CREATE TABLE contexts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    class_id    INTEGER NOT NULL,
    class_order INTEGER NOT NULL,  -- position within manual ordering of contexts within a class
    available   DATE NOT NULL,  -- date on which this context will be available to students (& mindate=available, maxdate=disabled)
    config      TEXT NOT NULL DEFAULT "{}",  -- JSON containing context config options
    created     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id)
);
-- names must be unique within a class, and we often look up by class and name
CREATE UNIQUE INDEX  contexts_by_class_name ON contexts(class_id, name);

-- Copy existing class configs into contexts
INSERT INTO contexts (name, class_id, class_order, available, config)
  SELECT 'Default', classes.id, 0, "0001-01-01", classes.config FROM classes;

-- Remove class config column
ALTER TABLE classes DROP COLUMN config;

COMMIT;
