-- SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

UPDATE models SET active=false WHERE model='gpt-4.1-nano';

COMMIT;

PRAGMA foreign_keys = ON;
