-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = ON;


CREATE TABLE consumers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lti_consumer  TEXT NOT NULL UNIQUE,
    lti_secret    TEXT,
    llm_api_key   TEXT,
    model_id      INTEGER NOT NULL,
    created       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(model_id) REFERENCES models(id)
);
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
    display_extra TEXT GENERATED ALWAYS AS (IIF(auth_provider = 5, '@' || auth_name, email)) VIRTUAL,  -- 5=Github, use @authname; else use email (okay if null)
    is_admin      BOOLEAN NOT NULL CHECK (is_admin IN (0,1)) DEFAULT 0,
    is_tester     BOOLEAN NOT NULL CHECK (is_tester IN (0,1)) DEFAULT 0,
    query_tokens  INTEGER NOT NULL DEFAULT 0,  -- number of tokens left for making queries - 0 means cut off
    created       DATETIME DEFAULT CURRENT_TIMESTAMP,
    delete_status TEXT CHECK (delete_status IN ('', 'deleted', 'whitelisted')) DEFAULT '',
    FOREIGN KEY(auth_provider) REFERENCES auth_providers(id)
);
-- user row to link for deleted roles
INSERT INTO users (id, auth_provider, full_name) VALUES (-1, 1, '[deleted]');


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
    is_anon       BOOLEAN NOT NULL CHECK (is_anon IN (0,1)) DEFAULT 0,  -- registered anonymously
    created       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(auth_provider) REFERENCES auth_providers(id)
);
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
CREATE UNIQUE INDEX  classes_lti_by_consumer_context ON classes_lti(lti_consumer_id, lti_context_id);

-- Classes created by a user, accessed via class link
CREATE TABLE classes_user (
    class_id         INTEGER PRIMARY KEY,  -- references classes.id
    llm_api_key      TEXT,
    model_id         INTEGER NOT NULL,
    link_ident       TEXT NOT NULL UNIQUE,  -- random (unguessable) identifier used in access/registration link for this class
    link_reg_expires DATE NOT NULL,  -- registration active for the class link if this date is in the future (anywhere on Earth)
    link_anon_login  BOOLEAN NOT NULL CHECK (link_anon_login IN (0,1)) DEFAULT 0,  -- access link will cause new users to register anonymously
    creator_user_id  INTEGER NOT NULL,  -- references users.id
    created          DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id),
    FOREIGN KEY(model_id) REFERENCES models(id),
    FOREIGN KEY(creator_user_id) REFERENCES users(id)
);
CREATE UNIQUE INDEX  classes_user_by_link_ident ON classes_user(link_ident);

-- Roles for users in classes
CREATE TABLE roles (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    role     TEXT NOT NULL CHECK( role IN ('instructor', 'student') ),
    active   BOOLEAN NOT NULL CHECK (active IN (0,1)) DEFAULT 1,  -- if not active, the user has no permissions in the class
    created  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(class_id) REFERENCES classes(id)
);
CREATE UNIQUE INDEX  roles_user_class_unique ON roles(user_id, class_id) WHERE user_id != -1;  -- not unique for deleted users
CREATE INDEX roles_by_class_id ON roles(class_id);

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
CREATE TABLE llm_providers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    endpoint        TEXT  -- can be null if overridden in models table
);

CREATE TABLE models (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id     INTEGER NOT NULL,
    shortname       TEXT NOT NULL UNIQUE,
    model           TEXT NOT NULL,
    custom_endpoint TEXT,  -- can be null to use default from providers table
    default_params  TEXT NOT NULL DEFAULT '{}',
    active          BOOLEAN NOT NULL CHECK (active IN (0,1)),
    owner_id        INTEGER,  -- leave NULL for system-owned/scoped models
    scope           TEXT GENERATED ALWAYS AS (IIF(owner_id IS NULL, 'system', 'user')) VIRTUAL,
    FOREIGN KEY(provider_id) REFERENCES llm_providers(id),
    FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX models_by_shortname_owner ON models(shortname, owner_id);

INSERT INTO llm_providers(name) VALUES ("Custom");
INSERT INTO llm_providers(name, endpoint) VALUES ('OpenAI', 'https://api.openai.com/v1');
INSERT INTO llm_providers(name, endpoint) VALUES ('Google', 'https://generativelanguage.googleapis.com/v1beta/openai/');

-- See also: DEFAULT_CLASS_MODEL_SHORTNAME in base.create_app_base()
INSERT INTO models(provider_id, shortname, model, default_params, active, owner_id) VALUES
    ((SELECT id FROM llm_providers WHERE name='OpenAI'), 'GPT-4.1', 'gpt-4.1', '{}', true, NULL),
    ((SELECT id FROM llm_providers WHERE name='OpenAI'), 'GPT-4.1 mini', 'gpt-4.1-mini', '{}', true, NULL),
    ((SELECT id FROM llm_providers WHERE name='OpenAI'), 'GPT-4.1 nano', 'gpt-4.1-nano', '{}', true, NULL),
    ((SELECT id FROM llm_providers WHERE name='Google'), 'Gemini 3 Flash Preview', 'gemini-3-flash-preview', '{}', true, NULL)
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
CREATE INDEX exp_crs_experiment_idx ON experiment_class(experiment_id);
CREATE INDEX exp_crs_class_idx ON experiment_class(class_id);


-- Enable/disable components per-class (if no row here, use default state for the component)
CREATE TABLE class_components (
    class_id INTEGER NOT NULL,
    component_name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL CHECK (enabled IN (0, 1)),
    created DATETIME DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (class_id, component_name),
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
);

