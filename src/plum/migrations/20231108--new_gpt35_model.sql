-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

UPDATE models
  SET chat_model="gpt-3.5-turbo-1106"
  WHERE id=1;

COMMIT;
