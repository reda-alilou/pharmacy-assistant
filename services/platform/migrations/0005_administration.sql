ALTER TABLE platform.users ADD COLUMN permissions_revision integer NOT NULL DEFAULT 1 CHECK (permissions_revision > 0);
ALTER TABLE platform.datasets ADD COLUMN suspended boolean NOT NULL DEFAULT false;
ALTER TABLE platform.datasets ADD COLUMN suspension_reason text NOT NULL DEFAULT '' CHECK (length(suspension_reason) <= 1000);
ALTER TABLE platform.datasets ADD COLUMN suspension_changed_at timestamptz;
ALTER TABLE platform.datasets ADD COLUMN suspension_changed_by uuid REFERENCES platform.users(id);
ALTER TABLE platform.datasets ADD CONSTRAINT suspension_record CHECK (NOT suspended OR (length(btrim(suspension_reason)) > 0 AND suspension_changed_at IS NOT NULL AND suspension_changed_by IS NOT NULL));
CREATE INDEX datasets_moderation_idx ON platform.datasets(suspended,updated_at DESC,id);
CREATE INDEX activity_actor_idx ON platform.activity(actor_id,id DESC);
CREATE INDEX activity_action_idx ON platform.activity(action,id DESC);
CREATE INDEX activity_resource_idx ON platform.activity(resource_kind,resource_id,id DESC);
CREATE INDEX users_permissions_idx ON platform.users(role,active,id);

-- The same transaction lock is used by the explicit CLI and HTTP administration.
-- Profile/password writes need no global admin lock. Permission changes still
-- serialize the invariant, and every affected account session is revoked.
CREATE OR REPLACE FUNCTION platform.guard_admin() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' OR NEW.role IS DISTINCT FROM OLD.role OR NEW.active IS DISTINCT FROM OLD.active THEN
    PERFORM pg_advisory_xact_lock(72419021);
    IF OLD.role = 'admin' AND OLD.active AND
       (TG_OP = 'DELETE' OR NEW.role <> 'admin' OR NOT NEW.active) THEN
      IF NOT EXISTS (SELECT 1 FROM platform.users WHERE role = 'admin' AND active AND id <> OLD.id) THEN
        RAISE EXCEPTION 'last active administrator' USING ERRCODE = '23514';
      END IF;
    END IF;
    IF TG_OP <> 'DELETE' THEN NEW.permissions_revision = OLD.permissions_revision + 1; END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  IF NEW.active IS DISTINCT FROM OLD.active OR NEW.role IS DISTINCT FROM OLD.role OR NEW.password_hash IS DISTINCT FROM OLD.password_hash THEN
    DELETE FROM platform.sessions WHERE user_id = OLD.id;
  END IF;
  RETURN NEW;
END $$;

ALTER TABLE platform.activity DROP CONSTRAINT activity_action_check;
ALTER TABLE platform.activity ADD CONSTRAINT activity_action_check CHECK (action IN (
  'account.registered','account.provisioned','account.updated','account.password_changed','account.permissions_changed',
  'import.uploaded','import.validation_failed','import.succeeded','import.cancelled',
  'dataset.updated','dataset.archived','dataset.deleted','dataset.version_created',
  'dataset.suspended','dataset.resumed','dataset.inspected',
  'analysis.created','analysis.updated','analysis.deleted','analysis.copied',
  'dashboard.created','dashboard.updated','dashboard.deleted','dashboard.copied',
  'sharing.granted','sharing.revoked','sharing.authorized','sharing.authorization_revoked'
));
-- Correct the outcome of already-recorded validation failures without altering
-- their actor, reason counts, timestamps or source data.
UPDATE platform.activity SET outcome='failure' WHERE action='import.validation_failed' AND outcome='success';
