-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE classes_user ADD COLUMN
    link_reg_expires DATE NOT NULL DEFAULT "0000-01-01";  -- registration active for the class link if this date is in the future (anywhere on Earth)

UPDATE classes_user
    SET link_reg_expires = IIF(link_reg_active=1, "9999-12-31", "2000-01-01");

ALTER TABLE classes_user DROP COLUMN link_reg_active;

COMMIT;
