-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA synchronous = NORMAL;  -- recommended setting for WAL mode
PRAGMA busy_timeout = 5000;   -- to avoid immediate errors on some blocked writes

