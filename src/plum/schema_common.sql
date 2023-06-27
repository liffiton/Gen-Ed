PRAGMA foreign_keys = OFF;  -- just for not worrying about table deletion order

DROP TABLE IF EXISTS consumers;
DROP TABLE IF EXISTS auth_providers;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS auth_local;
DROP TABLE IF EXISTS auth_external;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS classes;
DROP TABLE IF EXISTS demo_links;

PRAGMA foreign_keys = ON;  -- back on for good

CREATE TABLE consumers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lti_consumer  TEXT NOT NULL UNIQUE,
    lti_secret    TEXT,
    openai_key    TEXT,
    created       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    ('github')
;

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    auth_provider INTEGER NOT NULL,
    full_name     TEXT,
    email         TEXT,
    auth_name     TEXT,
    display_name  TEXT GENERATED ALWAYS AS (COALESCE(full_name, email, auth_name)) VIRTUAL NOT NULL,  -- NOT NULL on COALESCE effectively requires one of full_name, email, and auth_name
    is_admin      BOOLEAN NOT NULL CHECK (is_admin IN (0,1)) DEFAULT 0,
    is_tester     BOOLEAN NOT NULL CHECK (is_tester IN (0,1)) DEFAULT 0,
    query_tokens  INTEGER NOT NULL DEFAULT 0,  -- number of tokens left for making queries - 0 means cut off
    created       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(auth_provider) REFERENCES auth_providers(id)
);


CREATE TABLE auth_local (
    user_id       INTEGER PRIMARY KEY,
    username      TEXT NOT NULL,
    password      TEXT NOT NULL,
    created       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE auth_external (
    user_id       INTEGER PRIMARY KEY,
    auth_provider INTEGER NOT NULL,
    ext_id        TEXT NOT NULL,  -- the primary, unique ID used by the external provider
    created       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(auth_provider) REFERENCES auth_providers(id)
);
DROP INDEX IF EXISTS auth_external_by_ext_id;
CREATE UNIQUE INDEX auth_external_by_ext_id ON auth_external(auth_provider, ext_id);


-- Classes and their config
-- (superset type for classes_lti and classes_user)
-- Config stored as JSON for flexibility, esp. during development
CREATE TABLE classes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    enabled  BOOLEAN NOT NULL CHECK (enabled IN (0,1)) DEFAULT 1,
    config   TEXT NOT NULL DEFAULT "{}",  -- JSON containing class config options
    created  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Classes created/accessed via LTI
CREATE TABLE classes_lti (
    class_id          INTEGER PRIMARY KEY,  -- references classes.id
    lti_consumer_id   INTEGER NOT NULL,  -- references consumers.id
    lti_context_id    TEXT NOT NULL,  -- class ID from the LMS
    created           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id),
    FOREIGN KEY(lti_consumer_id) REFERENCES consumers(id)
);
DROP INDEX IF EXISTS classes_lti_by_consumer_context;
CREATE UNIQUE INDEX  classes_lti_by_consumer_context ON classes_lti(lti_consumer_id, lti_context_id);

-- Classes created by a user, accessed via class link
CREATE TABLE classes_user (
    class_id         INTEGER PRIMARY KEY,  -- references classes.id
    openai_key       TEXT,
    link_ident       TEXT NOT NULL UNIQUE,  -- random (unguessable) identifier used in access/registration link for this class
    link_reg_active  BOOLEAN NOT NULL CHECK (link_reg_active IN (0,1)) DEFAULT 0,  -- is registration active for the class link currently
    creator_user_id  INTEGER NOT NULL,  -- references users.id
    created          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id),
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

-- Store/manage demonstration links
CREATE TABLE demo_links (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE,
    enabled BOOLEAN NOT NULL CHECK (enabled IN (0,1)) DEFAULT 0,
    expiration DATE NOT NULL,
    tokens  INTEGER NOT NULL,  -- default number of query tokens to give newly-created users
    uses    INTEGER NOT NULL DEFAULT 0
);
