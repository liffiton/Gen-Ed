-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE roles ADD COLUMN active BOOLEAN NOT NULL CHECK (active IN (0,1)) DEFAULT 1;

COMMIT;
