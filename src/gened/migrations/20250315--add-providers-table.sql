-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;


-- Add providers table
CREATE TABLE llm_providers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    endpoint        TEXT,  -- can be null if overridden in models table
    config_schema   TEXT NOT NULL DEFAULT '{}'
);

-- Provider for existing OpenAI models
INSERT INTO llm_providers(name, endpoint, config_schema) VALUES
    ('OpenAI', 'https://api.openai.com/v1', '{
        "type": "object",
        "properties": {
            "temperature": {
                "type": "number",
                "minimum": 0,
                "maximum": 2,
                "default": 0.25
            },
            "max_tokens": {
                "type": "integer", 
                "minimum": 1,
                "default": 2000
            }
        }
    }');


-- Add provider reference and config to models
CREATE TABLE __new_models (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id     INTEGER NOT NULL,
    shortname       TEXT NOT NULL UNIQUE,
    model           TEXT NOT NULL,
    custom_endpoint TEXT,  -- can be null to use default from providers table
    config          TEXT NOT NULL DEFAULT '{}',  -- defaults from llm_providers.config_schema will be used for anything not specified here
    active          BOOLEAN NOT NULL CHECK (active IN (0,1)),
    FOREIGN KEY(provider_id) REFERENCES llm_providers(id)
);

-- Shift data from existing table
INSERT INTO __new_models (id, provider_id, shortname, model, active)
    SELECT
        id,
        (SELECT id FROM llm_providers WHERE name = 'OpenAI'),
        shortname,
        model,
        active
    FROM models;

-- overwrite table
DROP TABLE models;
ALTER TABLE __new_models RENAME TO models;


COMMIT;

PRAGMA foreign_keys = ON;
