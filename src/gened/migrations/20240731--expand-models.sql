-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

-- Note: Not removing DEFAULT values on model_id in consumer and classes_user.
--       With the default removed in the schema, no code going forward should
--       ever use that default (else it would crash in testing).

DROP TABLE models;

CREATE TABLE models (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    shortname   TEXT NOT NULL UNIQUE,
    model       TEXT NOT NULL,
    active      BOOLEAN NOT NULL CHECK (active IN (0,1))
);
-- See also: DEFAULT_MODEL_ID in app.config (src/gened/base.py)
INSERT INTO models(name, shortname, model, active) VALUES
    ('OpenAI GPT-3.5 Turbo', 'GPT-3.5', 'gpt-3.5-turbo-0125', false),
    ('OpenAI GPT-4o', 'GPT-4o', 'gpt-4o', true),
    ('OpenAI GPT-4o-mini', 'GPT-4o-mini', 'gpt-4o-mini', true)
;

COMMIT;

PRAGMA foreign_keys = ON;
