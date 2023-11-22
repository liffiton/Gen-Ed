BEGIN;

ALTER TABLE models
  DROP COLUMN text_model;
ALTER TABLE models
  RENAME chat_model to model;

COMMIT;
