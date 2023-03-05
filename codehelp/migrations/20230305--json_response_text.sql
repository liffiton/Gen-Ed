BEGIN;

UPDATE queries SET response_text=json_object('main', response_text);

COMMIT;
