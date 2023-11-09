BEGIN;

UPDATE models
  SET chat_model="gpt-3.5-turbo-1106"
  WHERE id=1;

COMMIT;
