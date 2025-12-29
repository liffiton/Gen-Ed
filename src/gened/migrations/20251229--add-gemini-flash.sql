-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

INSERT INTO llm_providers(name, endpoint) VALUES ('Google', 'https://generativelanguage.googleapis.com/v1beta/openai/');

INSERT INTO models(provider_id, shortname, model, default_params, active, owner_id) VALUES
    ((SELECT id FROM llm_providers WHERE name='Google'), 'Gemini 3 Flash Preview', 'gemini-3-flash-preview', '{}', true, NULL)
;


COMMIT;
