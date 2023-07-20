BEGIN;

CREATE TABLE consumers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lti_consumer  TEXT NOT NULL UNIQUE,
    lti_secret    TEXT,
    openai_key    TEXT
);

CREATE UNIQUE INDEX consumers_idx ON consumers(lti_consumer);

COMMIT;
