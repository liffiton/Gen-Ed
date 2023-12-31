-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;

-- Models (LLMs via API) to be assigned per-consumer or per-class
CREATE TABLE models (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    text_model  TEXT,
    chat_model  TEXT
);
INSERT INTO models(name, text_model, chat_model) VALUES
    ('OpenAI GPT-3.5', 'text-davinci-003', 'gpt-3.5-turbo'),
    ('OpenAI GPT-4', NULL, 'gpt-4')   -- GPT-4 only has a chat completion
;

CREATE TABLE __new_consumers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lti_consumer  TEXT NOT NULL UNIQUE,
    lti_secret    TEXT,
    openai_key    TEXT,
    model_id      INTEGER NOT NULL DEFAULT 1,  -- gpt-3.5
    created       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(model_id) REFERENCES models(id)
);
INSERT INTO __new_consumers (id, lti_consumer, lti_secret, openai_key, model_id, created)
    SELECT
        consumers.id,
        consumers.lti_consumer,
        consumers.lti_secret,
        consumers.openai_key,
        1,
        consumers.created
    FROM consumers;
DROP TABLE consumers;
ALTER TABLE __new_consumers RENAME TO consumers;

DROP INDEX IF EXISTS consumers_idx;
CREATE UNIQUE INDEX consumers_idx ON consumers(lti_consumer);


CREATE TABLE __new_classes_user (
    class_id         INTEGER PRIMARY KEY,  -- references classes.id
    openai_key       TEXT,
    model_id         INTEGER NOT NULL DEFAULT 1,  -- gpt-3.5
    link_ident       TEXT NOT NULL UNIQUE,  -- random (unguessable) identifier used in access/registration link for this class
    link_reg_expires DATE NOT NULL,  -- registration active for the class link if this date is in the future (anywhere on Earth)
    creator_user_id  INTEGER NOT NULL,  -- references users.id
    created          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id),
    FOREIGN KEY(model_id) REFERENCES models(id),
    FOREIGN KEY(creator_user_id) REFERENCES users(id)
);
INSERT INTO __new_classes_user (class_id, openai_key, model_id, link_ident, link_reg_expires, creator_user_id, created)
    SELECT
        classes_user.class_id,
        classes_user.openai_key,
        1,
        classes_user.link_ident,
        classes_user.link_reg_expires,
        classes_user.creator_user_id,
        classes_user.created
    FROM classes_user;
DROP TABLE classes_user;
ALTER TABLE __new_classes_user RENAME TO classes_user;

DROP INDEX IF EXISTS classes_user_by_link_ident;
CREATE UNIQUE INDEX  classes_user_by_link_ident ON classes_user(link_ident);


COMMIT;

PRAGMA foreign_keys = ON;
