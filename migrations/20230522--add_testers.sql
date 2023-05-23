BEGIN;

ALTER TABLE users ADD COLUMN is_tester BOOLEAN NOT NULL CHECK (is_tester IN (0,1)) DEFAULT 0;
UPDATE users SET is_tester=1 WHERE username='mark';

COMMIT;
