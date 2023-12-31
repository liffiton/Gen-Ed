-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE queries ADD COLUMN
  helpful BOOLEAN CHECK (helpful in (0, 1));

ALTER TABLE queries ADD COLUMN
  helpful_emoji TEXT GENERATED ALWAYS AS (CASE helpful WHEN 1 THEN '✅' WHEN 0 THEN '❌' ELSE '' END) VIRTUAL;

COMMIT;
