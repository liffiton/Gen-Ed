-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

-- Context strings are recorded for deduplication of rendered prompt strings
-- (used by the code_queries component via foreign key)
DROP TABLE IF EXISTS context_strings;
CREATE TABLE context_strings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ctx_str TEXT NOT NULL UNIQUE
);
