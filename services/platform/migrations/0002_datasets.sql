CREATE TABLE platform.datasets (
  id uuid PRIMARY KEY,
  owner_id uuid NOT NULL REFERENCES platform.users(id),
  title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 160),
  description text NOT NULL DEFAULT '' CHECK (length(description) <= 4000),
  category text NOT NULL DEFAULT '' CHECK (length(category) <= 100),
  source text NOT NULL DEFAULT '' CHECK (length(source) <= 500),
  observation_date date,
  archived boolean NOT NULL DEFAULT false,
  revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX datasets_owner_idx ON platform.datasets(owner_id, archived, updated_at DESC);

CREATE TABLE platform.import_receipts (
  id uuid PRIMARY KEY,
  owner_id uuid NOT NULL REFERENCES platform.users(id),
  dataset_id uuid REFERENCES platform.datasets(id) ON DELETE SET NULL,
  filename text NOT NULL CHECK (length(filename) BETWEEN 1 AND 255),
  source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
  byte_count integer NOT NULL CHECK (byte_count > 0 AND byte_count <= 10485760),
  status text NOT NULL CHECK (status IN ('uploaded','invalid','validated','imported','expired','cancelled')),
  issue_count integer NOT NULL DEFAULT 0 CHECK (issue_count >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);
CREATE INDEX import_receipts_owner_idx ON platform.import_receipts(owner_id, created_at DESC);

CREATE TABLE platform.import_uploads (
  receipt_id uuid PRIMARY KEY REFERENCES platform.import_receipts(id) ON DELETE CASCADE,
  content bytea NOT NULL,
  configuration jsonb,
  validation jsonb,
  revision integer NOT NULL DEFAULT 0 CHECK (revision >= 0),
  expires_at timestamptz NOT NULL DEFAULT (now()+interval '1 hour'),
  CHECK (configuration IS NULL OR jsonb_typeof(configuration)='object'),
  CHECK (validation IS NULL OR jsonb_typeof(validation)='object')
);
CREATE INDEX import_uploads_expiry_idx ON platform.import_uploads(expires_at);

CREATE TABLE platform.dataset_versions (
  id uuid PRIMARY KEY,
  dataset_id uuid NOT NULL REFERENCES platform.datasets(id) ON DELETE CASCADE,
  receipt_id uuid NOT NULL UNIQUE REFERENCES platform.import_receipts(id),
  version_number integer NOT NULL CHECK (version_number > 0),
  row_count integer NOT NULL CHECK (row_count BETWEEN 1 AND 25000),
  column_count integer NOT NULL CHECK (column_count BETWEEN 1 AND 100),
  configuration jsonb NOT NULL CHECK (jsonb_typeof(configuration)='object'),
  source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
  filename text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (dataset_id, version_number),
  UNIQUE (dataset_id, id)
);
CREATE INDEX dataset_versions_dataset_idx ON platform.dataset_versions(dataset_id,version_number DESC);

CREATE TABLE platform.dataset_columns (
  version_id uuid NOT NULL REFERENCES platform.dataset_versions(id) ON DELETE CASCADE,
  id text NOT NULL CHECK (id ~ '^c_[a-f0-9]{16}$'),
  ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 99),
  original_name text NOT NULL,
  display_name text NOT NULL,
  data_type text NOT NULL CHECK (data_type IN ('text','integer','decimal','boolean','date','datetime')),
  interpretation jsonb NOT NULL CHECK (jsonb_typeof(interpretation)='object'),
  profile jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(profile)='object'),
  PRIMARY KEY(version_id,id), UNIQUE(version_id,ordinal)
);

CREATE TABLE platform.dataset_rows (
  version_id uuid NOT NULL REFERENCES platform.dataset_versions(id) ON DELETE CASCADE,
  row_number integer NOT NULL CHECK (row_number BETWEEN 1 AND 25000),
  source_line integer NOT NULL CHECK (source_line > 1),
  values jsonb NOT NULL CHECK (jsonb_typeof(values)='object'),
  original_values jsonb NOT NULL CHECK (jsonb_typeof(original_values)='object'),
  PRIMARY KEY(version_id,row_number)
);

-- Dependency registration is a deletion safeguard for later analyses/shares.
-- No analysis or sharing workflow is implemented by this table.
CREATE TABLE platform.dataset_dependencies (
  id uuid PRIMARY KEY,
  dataset_id uuid NOT NULL REFERENCES platform.datasets(id),
  version_id uuid,
  kind text NOT NULL CHECK (kind IN ('analysis','dashboard','share')),
  resource_id uuid NOT NULL,
  label text NOT NULL,
  FOREIGN KEY(dataset_id,version_id) REFERENCES platform.dataset_versions(dataset_id,id),
  UNIQUE NULLS NOT DISTINCT(dataset_id,version_id,kind,resource_id)
);
CREATE INDEX dataset_dependencies_dataset_idx ON platform.dataset_dependencies(dataset_id);

ALTER TABLE platform.activity DROP CONSTRAINT activity_action_check;
ALTER TABLE platform.activity DROP CONSTRAINT activity_resource_id_fkey;
ALTER TABLE platform.activity ADD COLUMN resource_kind text NOT NULL DEFAULT 'account' CHECK (resource_kind IN ('account','dataset','import'));
ALTER TABLE platform.activity ADD CONSTRAINT activity_action_check CHECK (action IN (
  'account.registered','account.provisioned','account.updated','account.password_changed','account.permissions_changed',
  'import.uploaded','import.validation_failed','import.succeeded','import.cancelled',
  'dataset.updated','dataset.archived','dataset.deleted'
));
