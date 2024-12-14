-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE consumers RENAME COLUMN openai_key TO llm_api_key;
ALTER TABLE classes_user RENAME COLUMN openai_key TO llm_api_key;

COMMIT;
