-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

INSERT INTO models(name, model) VALUES
    ('OpenAI GPT-4 Turbo', 'gpt-4-1106-preview')
;

COMMIT;
