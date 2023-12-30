-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE users ADD COLUMN
    last_role_id  INTEGER;  -- most recently activated role (note: may no longer exist if deleted) used to re-activate on login

COMMIT;
