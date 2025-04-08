-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

-- Add scopes to models
CREATE TABLE __new_models (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id     INTEGER NOT NULL,
    shortname       TEXT NOT NULL UNIQUE,
    model           TEXT NOT NULL,
    custom_endpoint TEXT,  -- can be null to use default from providers table
    config          TEXT NOT NULL DEFAULT '{}',  -- defaults from llm_providers.config_schema will be used for anything not specified here
    active          BOOLEAN NOT NULL CHECK (active IN (0,1)),
    scope           TEXT NOT NULL CHECK (scope IN ('system', 'user')),
    owner_id        INTEGER,
    CHECK ((scope = 'system' AND owner_id IS NULL) OR
           (scope = 'user' AND owner_id IS NOT NULL)),
    FOREIGN KEY(provider_id) REFERENCES llm_providers(id),
    FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Shift data from existing table
INSERT INTO __new_models (id, provider_id, shortname, model, active, scope, owner_id)
    SELECT
        id,
        provider_id,
        shortname,
        model,
        active,
        'system',
        NULL
    FROM models;

-- overwrite table
DROP TABLE models;
ALTER TABLE __new_models RENAME TO models;


COMMIT;

PRAGMA foreign_keys = ON;
