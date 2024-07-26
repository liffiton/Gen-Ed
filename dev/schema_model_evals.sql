-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;  -- just for not worrying about table deletion order

DROP TABLE IF EXISTS prompt;
DROP TABLE IF EXISTS prompt_set;
DROP TABLE IF EXISTS response;
DROP TABLE IF EXISTS response_set;
DROP TABLE IF EXISTS eval_prompt;
DROP TABLE IF EXISTS eval;
DROP TABLE IF EXISTS eval_set;

PRAGMA foreign_keys = ON;  -- back on for good

CREATE TABLE prompt (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id      INTEGER NOT NULL,
    msgs_json   TEXT NOT NULL,
    model_response  TEXT NOT NULL,  -- A model response for this prompt -- form depends on the type of prompt
    FOREIGN KEY(set_id) REFERENCES prompt_set(id) ON DELETE CASCADE
);

CREATE TABLE prompt_set (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    query_src_file   TEXT NOT NULL,
    prompt_func TEXT NOT NULL
);

CREATE TABLE response (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id      INTEGER NOT NULL,
    prompt_id   INTEGER NOT NULL,
    response    TEXT NOT NULL,  -- full json response object
    text        TEXT NOT NULL,  -- just the text
    FOREIGN KEY(prompt_id) REFERENCES prompt(id),
    FOREIGN KEY(set_id) REFERENCES response_set(id) ON DELETE CASCADE
);

CREATE TABLE response_set (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    prompt_set_id  INTEGER NOT NULL,
    model       TEXT NOT NULL,
    FOREIGN KEY(prompt_set_id) REFERENCES prompt_set(id)
);


CREATE TABLE eval_prompt (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sys_prompt  TEXT NOT NULL UNIQUE
);

CREATE TABLE eval (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id      INTEGER NOT NULL,
    response_id INTEGER NOT NULL,
    evaluation  TEXT NOT NULL,  -- full json response object
    FOREIGN KEY(response_id) REFERENCES response(id),
    FOREIGN KEY(set_id) REFERENCES eval_set(id) ON DELETE CASCADE
);

CREATE TABLE eval_set (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    response_set_id INTEGER NOT NULL,
    eval_prompt_id INTEGER NOT NULL,
    model       TEXT NOT NULL,
    FOREIGN KEY(response_set_id) REFERENCES response_set(id)
    FOREIGN KEY(eval_prompt_id) REFERENCES eval_prompt(id)
);

