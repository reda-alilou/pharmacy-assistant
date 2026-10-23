CREATE SCHEMA IF NOT EXISTS platform;
REVOKE ALL ON SCHEMA platform FROM PUBLIC;

CREATE TABLE platform.users (
  id uuid PRIMARY KEY,
  email text COLLATE "C" NOT NULL UNIQUE CHECK (email = lower(btrim(email)) AND length(email) BETWEEN 3 AND 254),
  display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 80),
  password_hash text NOT NULL,
  role text NOT NULL DEFAULT 'analyst' CHECK (role IN ('analyst', 'admin')),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE platform.sessions (
  token_hash text PRIMARY KEY CHECK (token_hash ~ '^[a-f0-9]{64}$'),
  user_id uuid REFERENCES platform.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  absolute_expires_at timestamptz NOT NULL,
  CHECK (expires_at <= absolute_expires_at AND created_at < absolute_expires_at)
);
CREATE INDEX sessions_user_idx ON platform.sessions(user_id);
CREATE INDEX sessions_expiry_idx ON platform.sessions(expires_at);

CREATE TABLE platform.auth_throttles (
  key_hash text PRIMARY KEY CHECK (key_hash ~ '^[a-f0-9]{64}$'),
  attempts integer NOT NULL CHECK (attempts > 0),
  expires_at timestamptz NOT NULL
);
CREATE INDEX auth_throttles_expiry_idx ON platform.auth_throttles(expires_at);

CREATE TABLE platform.activity (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  actor_id uuid REFERENCES platform.users(id),
  action text NOT NULL CHECK (action IN ('account.registered', 'account.provisioned', 'account.updated', 'account.password_changed', 'account.permissions_changed')),
  resource_id uuid NOT NULL REFERENCES platform.users(id),
  outcome text NOT NULL DEFAULT 'success' CHECK (outcome IN ('success', 'failure')),
  details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX activity_created_idx ON platform.activity(created_at);

-- Defense in depth: also protects administrative SQL and concurrent changes.
-- The explicit administration command takes the same lock before reading users.
CREATE FUNCTION platform.guard_admin() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(72419021);
  IF OLD.role = 'admin' AND OLD.active AND
     (TG_OP = 'DELETE' OR NEW.role <> 'admin' OR NOT NEW.active) THEN
    IF NOT EXISTS (SELECT 1 FROM platform.users WHERE role = 'admin' AND active AND id <> OLD.id) THEN
      RAISE EXCEPTION 'last active administrator' USING ERRCODE = '23514';
    END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  IF NEW.active IS DISTINCT FROM OLD.active OR NEW.role IS DISTINCT FROM OLD.role OR NEW.password_hash IS DISTINCT FROM OLD.password_hash THEN
    DELETE FROM platform.sessions WHERE user_id = OLD.id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_admin BEFORE UPDATE OR DELETE ON platform.users FOR EACH ROW EXECUTE FUNCTION platform.guard_admin();
