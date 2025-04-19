-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

INSERT INTO models(provider_id, shortname, model, active, scope) VALUES
    ((SELECT id FROM llm_providers WHERE name='OpenAI'), 'GPT-4.1', 'gpt-4.1', true, 'system'),
    ((SELECT id FROM llm_providers WHERE name='OpenAI'), 'GPT-4.1 mini', 'gpt-4.1-mini', true, 'system'),
    ((SELECT id FROM llm_providers WHERE name='OpenAI'), 'GPT-4.1 nano', 'gpt-4.1-nano', true, 'system')
;

UPDATE models SET active=false WHERE shortname="GPT-4o";
UPDATE models SET active=false WHERE shortname="GPT-4o-mini";

COMMIT;

PRAGMA foreign_keys = ON;
