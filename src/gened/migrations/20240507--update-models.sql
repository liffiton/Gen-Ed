-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

UPDATE models SET model="gpt-4-turbo-2024-04-09" WHERE model="gpt-4-0125-preview";

COMMIT;

PRAGMA foreign_keys = ON;
