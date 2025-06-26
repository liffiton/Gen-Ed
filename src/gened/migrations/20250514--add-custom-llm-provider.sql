-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

INSERT INTO llm_providers (name) VALUES ("Custom");
CREATE UNIQUE INDEX models_by_shortname_owner ON models(shortname, owner_id);

COMMIT;
