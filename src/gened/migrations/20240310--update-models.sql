-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

UPDATE models SET model="gpt-3.5-turbo-0125" WHERE model="gpt-3.5-turbo-1106";
UPDATE models SET model="gpt-4-0125-preview" WHERE model="gpt-4-1106-preview";

COMMIT;

PRAGMA foreign_keys = ON;
