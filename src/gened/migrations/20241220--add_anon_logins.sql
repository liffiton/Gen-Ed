-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE auth_external ADD COLUMN 
    is_anon       BOOLEAN NOT NULL CHECK (is_anon IN (0,1)) DEFAULT 0;  -- registered anonymously

COMMIT;
