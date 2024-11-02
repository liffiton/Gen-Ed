-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA journal_mode = WAL;    -- to enable Litestream backups
PRAGMA synchronous = NORMAL;  -- recommended setting for WAL mode
PRAGMA busy_timeout = 5000;   -- to avoid immediate errors on some blocked writes

PRAGMA foreign_keys = OFF;  -- just for not worrying about table deletion order

DROP TABLE IF EXISTS consumers;
DROP TABLE IF EXISTS auth_providers;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS auth_local;
DROP TABLE IF EXISTS auth_external;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS classes;
DROP TABLE IF EXISTS classes_lti;
DROP TABLE IF EXISTS classes_user;
DROP TABLE IF EXISTS demo_links;
DROP TABLE IF EXISTS migrations;
DROP TABLE IF EXISTS models;
DROP TABLE IF EXISTS experiments;
DROP TABLE IF EXISTS experiment_class;

PRAGMA foreign_keys = ON;  -- back on for good


CREATE TABLE consumers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lti_consumer  TEXT NOT NULL UNIQUE,
    lti_secret    TEXT,
    openai_key    TEXT,
    model_id      INTEGER NOT NULL,
    created       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(model_id) REFERENCES models(id)
);

DROP INDEX IF EXISTS consumers_idx;
CREATE UNIQUE INDEX consumers_idx ON consumers(lti_consumer);

CREATE TABLE auth_providers (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT NOT NULL
);
INSERT INTO auth_providers(name) VALUES
    ('local'),
    ('lti'),
    ('demo'),
    ('google'),
    ('github'),
    ('microsoft')
;

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    auth_provider INTEGER NOT NULL,
    last_class_id INTEGER,  -- most recently active class, used to re-activate on login (note: user may no longer have active role in this class)
    full_name     TEXT,
    email         TEXT,
    auth_name     TEXT,
    display_name  TEXT GENERATED ALWAYS AS (COALESCE(full_name, email, auth_name)) VIRTUAL NOT NULL,  -- NOT NULL on COALESCE effectively requires one of full_name, email, and auth_name
    is_admin      BOOLEAN NOT NULL CHECK (is_admin IN (0,1)) DEFAULT 0,
    is_tester     BOOLEAN NOT NULL CHECK (is_tester IN (0,1)) DEFAULT 0,
    query_tokens  INTEGER NOT NULL DEFAULT 0,  -- number of tokens left for making queries - 0 means cut off
    created       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(auth_provider) REFERENCES auth_providers(id)
);


CREATE TABLE auth_local (
    user_id       INTEGER PRIMARY KEY,
    username      TEXT NOT NULL,
    password      TEXT NOT NULL,
    created       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE auth_external (
    user_id       INTEGER PRIMARY KEY,
    auth_provider INTEGER NOT NULL,
    ext_id        TEXT NOT NULL,  -- the primary, unique ID used by the external provider
    created       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(auth_provider) REFERENCES auth_providers(id)
);
DROP INDEX IF EXISTS auth_external_by_ext_id;
CREATE UNIQUE INDEX auth_external_by_ext_id ON auth_external(auth_provider, ext_id);


-- Classes
-- (superset type for classes_lti and classes_user)
CREATE TABLE classes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    enabled  BOOLEAN NOT NULL CHECK (enabled IN (0,1)) DEFAULT 1,
    created  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Classes created/accessed via LTI
CREATE TABLE classes_lti (
    class_id          INTEGER PRIMARY KEY,  -- references classes.id
    lti_consumer_id   INTEGER NOT NULL,  -- references consumers.id
    lti_context_id    TEXT NOT NULL,  -- class ID from the LMS
    created           DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id),
    FOREIGN KEY(lti_consumer_id) REFERENCES consumers(id)
);
DROP INDEX IF EXISTS classes_lti_by_consumer_context;
CREATE UNIQUE INDEX  classes_lti_by_consumer_context ON classes_lti(lti_consumer_id, lti_context_id);

-- Classes created by a user, accessed via class link
CREATE TABLE classes_user (
    class_id         INTEGER PRIMARY KEY,  -- references classes.id
    openai_key       TEXT,
    model_id         INTEGER NOT NULL,
    link_ident       TEXT NOT NULL UNIQUE,  -- random (unguessable) identifier used in access/registration link for this class
    link_reg_expires DATE NOT NULL,  -- registration active for the class link if this date is in the future (anywhere on Earth)
    creator_user_id  INTEGER NOT NULL,  -- references users.id
    created          DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id),
    FOREIGN KEY(model_id) REFERENCES models(id),
    FOREIGN KEY(creator_user_id) REFERENCES users(id)
);
DROP INDEX IF EXISTS classes_user_by_link_ident;
CREATE UNIQUE INDEX  classes_user_by_link_ident ON classes_user(link_ident);

-- Roles for users in classes
CREATE TABLE roles (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    role     TEXT NOT NULL CHECK( role IN ('instructor', 'student') ),
    active   BOOLEAN NOT NULL CHECK (active IN (0,1)) DEFAULT 1,  -- if not active, the user has no permissions in the class
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(class_id) REFERENCES classes(id)
);
DROP INDEX IF EXISTS roles_user_class_unique;
CREATE UNIQUE INDEX  roles_user_class_unique ON roles(user_id, class_id);

-- Store/manage demonstration links
CREATE TABLE demo_links (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE,
    enabled BOOLEAN NOT NULL CHECK (enabled IN (0,1)) DEFAULT 0,
    expiration DATE NOT NULL,
    tokens  INTEGER NOT NULL,  -- default number of query tokens to give newly-created users
    uses    INTEGER NOT NULL DEFAULT 0
);

-- Track which migrations have been applied to this database
CREATE TABLE migrations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL UNIQUE,
    applied_on  DATETIME DEFAULT CURRENT_TIMESTAMP,
    skipped     BOOLEAN NOT NULL CHECK (skipped IN (0,1)) DEFAULT 0,
    succeeded   BOOLEAN NOT NULL CHECK (succeeded IN (0,1)) DEFAULT 0
);

-- Models (LLMs via API) to be assigned per-consumer or per-class
CREATE TABLE models (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    shortname   TEXT NOT NULL UNIQUE,
    model       TEXT NOT NULL,
    active      BOOLEAN NOT NULL CHECK (active IN (0,1))
);
-- See also: DEFAULT_CLASS_MODEL_SHORTNAME in base.create_app_base()
INSERT INTO models(name, shortname, model, active) VALUES
    ('OpenAI GPT-3.5 Turbo', 'GPT-3.5', 'gpt-3.5-turbo-0125', false),
    ('OpenAI GPT-4o', 'GPT-4o', 'gpt-4o', true),
    ('OpenAI GPT-4o-mini', 'GPT-4o-mini', 'gpt-4o-mini', true)
;


-- Experiments (like feature flags)
CREATE TABLE experiments (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE,
    description  TEXT
);

CREATE TABLE experiment_class (
    experiment_id   INTEGER NOT NULL,
    class_id        INTEGER NOT NULL,
    PRIMARY KEY (experiment_id, class_id),
    FOREIGN KEY (experiment_id) REFERENCES experiments (id),
    FOREIGN KEY (class_id) REFERENCES classes (id)
);
DROP INDEX IF EXISTS exp_crs_experiment_idx;
CREATE INDEX exp_crs_experiment_idx ON experiment_class(experiment_id);
DROP INDEX IF EXISTS exp_crs_class_idx;
CREATE INDEX exp_crs_class_idx ON experiment_class(class_id);
