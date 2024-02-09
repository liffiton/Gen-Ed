-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

-- Remove old GPT-4
-- Currently, 2=GPT-4, 3=GPT-4-Turbo
-- 2 will be GPT-4-turbo in the new table, so change all 3 to 2.
UPDATE consumers SET model_id=2 WHERE model_id=3;
UPDATE classes_user SET model_id=2 WHERE model_id=3;

-- Add shortname column, drop old GPT-4 model
-- Adding a UNIQUE column, so have to recreate entire table
DROP TABLE models;
CREATE TABLE models (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    shortname   TEXT NOT NULL UNIQUE,
    model       TEXT
);
INSERT INTO models(name, shortname, model) VALUES
    ('OpenAI GPT-3.5 Turbo', 'GPT-3.5', 'gpt-3.5-turbo-1106'),
    ('OpenAI GPT-4 Turbo', 'GPT-4', 'gpt-4-1106-preview')
;

COMMIT;

PRAGMA foreign_keys = ON;
