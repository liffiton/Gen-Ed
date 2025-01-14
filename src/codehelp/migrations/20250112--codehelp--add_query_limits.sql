-- SPDX-FileCopyrightText: Mark Liffiton <liffiton@gmail.com>, Rana Moeez Hassan
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;
BEGIN;

-- Add columns to the classes table
ALTER TABLE classes ADD COLUMN query_limit_enabled BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE classes ADD COLUMN max_queries INTEGER NOT NULL DEFAULT 50;

-- Ensure the users table has a column to track the number of queries used
ALTER TABLE users ADD COLUMN queries_used INTEGER NOT NULL DEFAULT 0;

COMMIT;
PRAGMA foreign_keys = ON;