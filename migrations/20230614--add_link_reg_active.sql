BEGIN;

-- is registration active for the class link currently
ALTER TABLE classes_user ADD COLUMN link_reg_active  BOOLEAN NOT NULL CHECK (link_reg_active IN (0,1)) DEFAULT 0;

COMMIT;
