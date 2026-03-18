-- SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

INSERT OR IGNORE INTO models(provider_id, shortname, model, default_params, active, owner_id) VALUES
    ((SELECT id FROM llm_providers WHERE name='OpenAI'), 'GPT-5.4 mini', 'gpt-5.4-mini', '{"reasoning_effort": "medium", "temperature": 1}', true, NULL),
    ((SELECT id FROM llm_providers WHERE name='OpenAI'), 'GPT-5.4 nano', 'gpt-5.4-nano', '{"reasoning_effort": "high", "temperature": 1}', true, NULL)
;

UPDATE models SET active=false WHERE model='gpt-4.1';
UPDATE models SET active=false WHERE model='gpt-4.1-mini';

COMMIT;

PRAGMA foreign_keys = ON;
