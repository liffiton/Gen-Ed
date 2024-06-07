-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

UPDATE models SET name="OpenAI GPT-4o", shortname="GPT-4", model="gpt-4o" WHERE model="gpt-4-turbo-2024-04-09";

COMMIT;

PRAGMA foreign_keys = ON;
