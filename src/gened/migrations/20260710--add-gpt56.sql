-- SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

INSERT OR IGNORE INTO models(provider_id, shortname, model, default_params, active, owner_id) VALUES
    ((SELECT id FROM llm_providers WHERE name='OpenAI'), 'GPT-5.6 Luna', 'gpt-5.6-luna', '{"reasoning_effort": "medium"}', true, NULL)
;

UPDATE models SET active=false WHERE model='gpt-5.4-mini';

COMMIT;

PRAGMA foreign_keys = ON;
