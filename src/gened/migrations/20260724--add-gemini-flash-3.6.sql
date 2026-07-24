-- SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

INSERT OR IGNORE INTO models(provider_id, shortname, model, default_params, active, owner_id) VALUES
    ((SELECT id FROM llm_providers WHERE name='Google'), 'Gemini 3.6 Flash', 'gemini-3.6-flash', '{"reasoning_effort": "low"}', true, NULL)
;

COMMIT;
