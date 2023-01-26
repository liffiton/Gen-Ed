PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS queries;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,  -- ideally email
    password TEXT,  -- could be null if registered via LTI
    is_admin BOOLEAN NOT NULL CHECK (is_admin IN (0,1)) DEFAULT 0,
    lti_id   TEXT,  -- combination of LTI consumer, LTI userid, and email -- used to connect LTI sessions to users
    lti_consumer  TEXT  -- the LTI consumer that registered this user, if applicable
);

-- Record the LTI contexts and roles with which any user has connected to the service.
CREATE TABLE roles (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    lti_context  STRING NOT NULL,
    role     TEXT NOT NULL CHECK( role IN ('instructor', 'student') ),
    FOREIGN KEY(user_id) REFERENCES users(id)
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
    user_id INTEGER NOT NULL,
    role_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(role_id) REFERENCES roles(id)
);

