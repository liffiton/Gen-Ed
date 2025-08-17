-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE llm_providers DROP COLUMN config_schema;

ALTER TABLE models RENAME COLUMN config TO default_params;

COMMIT;
