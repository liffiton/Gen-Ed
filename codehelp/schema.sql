PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS queries;
DROP TABLE IF EXISTS consumers;
DROP INDEX IF EXISTS consumers_idx;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS classes;

CREATE TABLE consumers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lti_consumer  TEXT NOT NULL UNIQUE,
    lti_secret    TEXT,
    openai_key    TEXT
);

CREATE UNIQUE INDEX consumers_idx ON consumers(lti_consumer);

CREATE TABLE users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,  -- ideally email
    password TEXT,  -- could be null if registered via LTI
    is_admin BOOLEAN NOT NULL CHECK (is_admin IN (0,1)) DEFAULT 0,
    lti_id   TEXT UNIQUE,  -- combination of LTI consumer, LTI userid, and email -- used to connect LTI sessions to users
    lti_consumer  TEXT  -- the LTI consumer that registered this user, if applicable
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
    config            TEXT NOT NULL DEFAULT "{}"   -- JSON containing class config options
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

CREATE TABLE queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    language TEXT NOT NULL,
    code TEXT,
    error TEXT,
    issue TEXT NOT NULL,
    response_json TEXT,
    response_text TEXT,
    helpful BOOLEAN CHECK (helpful in (0, 1)),
    helpful_emoji TEXT GENERATED ALWAYS AS (CASE helpful WHEN 1 THEN '✅' WHEN 0 THEN '❌' ELSE '' END) VIRTUAL,
    user_id INTEGER NOT NULL,
    role_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(role_id) REFERENCES roles(id)
);
