-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

CREATE TABLE __new_models (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id     INTEGER NOT NULL,
    shortname       TEXT NOT NULL UNIQUE,
    model           TEXT NOT NULL,
    custom_endpoint TEXT,  -- can be null to use default from providers table
    config          TEXT NOT NULL DEFAULT '{}',  -- defaults from llm_providers.config_schema will be used for anything not specified here
    active          BOOLEAN NOT NULL CHECK (active IN (0,1)),
    owner_id        INTEGER,  -- leave NULL for system-owned/scoped models
    scope           TEXT GENERATED ALWAYS AS (IIF(owner_id IS NULL, 'system', 'user')) VIRTUAL,
    FOREIGN KEY(provider_id) REFERENCES llm_providers(id),
    FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE
);

INSERT INTO __new_models (id, provider_id, shortname, model, custom_endpoint, config, active, owner_id)
    SELECT id, provider_id, shortname, model, custom_endpoint, config, active, owner_id
    FROM models;

DROP INDEX IF EXISTS models_by_shortname_owner;

DROP TABLE models;

ALTER TABLE __new_models RENAME TO models;

CREATE UNIQUE INDEX models_by_shortname_owner ON models(shortname, owner_id);

COMMIT;

PRAGMA foreign_keys = ON;
