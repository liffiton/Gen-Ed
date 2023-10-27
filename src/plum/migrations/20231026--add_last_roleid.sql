BEGIN;

ALTER TABLE users ADD COLUMN
    last_role_id  INTEGER;  -- most recently activated role (note: may no longer exist if deleted) used to re-activate on login

COMMIT;
