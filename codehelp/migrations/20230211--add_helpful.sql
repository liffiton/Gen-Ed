BEGIN;

ALTER TABLE queries ADD COLUMN
  helpful BOOLEAN CHECK (helpful in (0, 1));

COMMIT;
