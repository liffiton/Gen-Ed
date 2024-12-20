-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE classes_user ADD COLUMN
    link_anon_login  BOOLEAN NOT NULL CHECK (link_anon_login IN (0,1)) DEFAULT 0;  -- access link will cause new users to register anonymously

COMMIT;
