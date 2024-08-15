-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

UPDATE models SET model="gpt-4o-2024-08-06" WHERE model="gpt-4o";
UPDATE models SET model="gpt-4o-mini-2024-07-18" WHERE model="gpt-4o-mini";

COMMIT;

PRAGMA foreign_keys = ON;
