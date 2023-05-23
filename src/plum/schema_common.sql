PRAGMA foreign_keys = OFF;  -- just for not worrying about table deletion order

DROP TABLE IF EXISTS consumers;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS classes;
DROP TABLE IF EXISTS demo_links;

PRAGMA foreign_keys = ON;

CREATE TABLE consumers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lti_consumer  TEXT NOT NULL UNIQUE,
    lti_secret    TEXT,
    openai_key    TEXT,
    created       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP INDEX IF EXISTS consumers_idx;
CREATE UNIQUE INDEX consumers_idx ON consumers(lti_consumer);

CREATE TABLE users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,  -- ideally email
    password TEXT,  -- could be null if registered via LTI
    is_admin BOOLEAN NOT NULL CHECK (is_admin IN (0,1)) DEFAULT 0,
    is_tester BOOLEAN NOT NULL CHECK (is_tester IN (0,1)) DEFAULT 0,
    lti_id   TEXT UNIQUE,  -- combination of LTI consumer, LTI userid, and email -- used to connect LTI sessions to users
    lti_consumer TEXT,  -- the LTI consumer that registered this user, if applicable
    query_tokens INTEGER,  -- number of tokens left for making queries - for demo users - default NULL means no limit
    created  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- require unique usernames if no LTI ID (allows multiple users w/ same username if coming from different LTI consumers)
DROP INDEX IF EXISTS unique_username_without_lti;
CREATE UNIQUE INDEX unique_username_without_lti ON users (username) WHERE lti_id IS NULL;

-- Record LTI contexts (classes) and their config
-- Config stored as JSON for flexibility, esp. during development
CREATE TABLE classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lti_consumer      TEXT NOT NULL,
    lti_context_id    TEXT NOT NULL,
    lti_context_label TEXT NOT NULL,  -- name of the class
    config            TEXT NOT NULL DEFAULT "{}",  -- JSON containing class config options
    created           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Record the LTI contexts and roles with which any user has connected to the service.
CREATE TABLE roles (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    role     TEXT NOT NULL CHECK( role IN ('instructor', 'student') ),
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
