-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

ALTER TABLE models
  DROP COLUMN text_model;
ALTER TABLE models
  RENAME chat_model to model;

COMMIT;
