-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE queries ADD COLUMN context_name TEXT;
ALTER TABLE queries ADD COLUMN context TEXT;
UPDATE queries SET context_name="migrated";
UPDATE queries SET context=language;
ALTER TABLE queries DROP COLUMN language;

COMMIT;
