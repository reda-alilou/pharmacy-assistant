CREATE TABLE platform.dashboards (
  id uuid PRIMARY KEY,
  owner_id uuid NOT NULL REFERENCES platform.users(id),
  title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 160),
  description text NOT NULL DEFAULT '' CHECK (length(description)<=4000),
  configuration jsonb NOT NULL CHECK (jsonb_typeof(configuration)='object' AND configuration->>'algorithm'='cp4-v1'),
  revision integer NOT NULL DEFAULT 1 CHECK (revision>0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX dashboards_owner_idx ON platform.dashboards(owner_id,updated_at DESC,id);
CREATE TABLE platform.dashboard_sources (
  dashboard_id uuid NOT NULL REFERENCES platform.dashboards(id) ON DELETE CASCADE,
  dataset_id uuid NOT NULL,
  version_id uuid NOT NULL,
  PRIMARY KEY(dashboard_id,version_id),
  FOREIGN KEY(dataset_id,version_id) REFERENCES platform.dataset_versions(dataset_id,id)
);
CREATE INDEX dashboard_sources_dataset_idx ON platform.dashboard_sources(dataset_id);
CREATE TABLE platform.dataset_grants (
  id uuid PRIMARY KEY,
  dataset_id uuid NOT NULL REFERENCES platform.datasets(id),
  recipient_id uuid NOT NULL REFERENCES platform.users(id),
  created_by uuid NOT NULL REFERENCES platform.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(dataset_id,recipient_id)
);
CREATE INDEX dataset_grants_recipient_idx ON platform.dataset_grants(recipient_id,dataset_id);
CREATE TABLE platform.dashboard_grants (
  id uuid PRIMARY KEY,
  dashboard_id uuid NOT NULL REFERENCES platform.dashboards(id) ON DELETE CASCADE,
  recipient_id uuid NOT NULL REFERENCES platform.users(id),
  created_by uuid NOT NULL REFERENCES platform.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(dashboard_id,recipient_id)
);
CREATE INDEX dashboard_grants_recipient_idx ON platform.dashboard_grants(recipient_id,dashboard_id);
CREATE TABLE platform.analysis_grants (
  id uuid PRIMARY KEY,
  analysis_id uuid NOT NULL REFERENCES platform.analyses(id) ON DELETE CASCADE,
  recipient_id uuid NOT NULL REFERENCES platform.users(id),
  created_by uuid NOT NULL REFERENCES platform.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(analysis_id,recipient_id)
);
CREATE INDEX analysis_grants_recipient_idx ON platform.analysis_grants(recipient_id,analysis_id);
-- Original dataset-owner authorization is specific to one saved resource revision.
-- Editing that resource makes an old authorization ineffective until renewed.
CREATE TABLE platform.dashboard_authorizations (
  dataset_id uuid NOT NULL REFERENCES platform.datasets(id),
  dashboard_id uuid NOT NULL REFERENCES platform.dashboards(id) ON DELETE CASCADE,
  revision integer NOT NULL CHECK (revision>0),
  authorized_by uuid NOT NULL REFERENCES platform.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(dataset_id,dashboard_id)
);
CREATE TABLE platform.analysis_authorizations (
  dataset_id uuid NOT NULL REFERENCES platform.datasets(id),
  analysis_id uuid NOT NULL REFERENCES platform.analyses(id) ON DELETE CASCADE,
  revision integer NOT NULL CHECK (revision>0),
  authorized_by uuid NOT NULL REFERENCES platform.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(dataset_id,analysis_id)
);
ALTER TABLE platform.activity DROP CONSTRAINT activity_resource_kind_check;
ALTER TABLE platform.activity ADD CONSTRAINT activity_resource_kind_check CHECK (resource_kind IN ('account','dataset','import','analysis','dashboard'));
ALTER TABLE platform.activity DROP CONSTRAINT activity_action_check;
ALTER TABLE platform.activity ADD CONSTRAINT activity_action_check CHECK (action IN (
  'account.registered','account.provisioned','account.updated','account.password_changed','account.permissions_changed',
  'import.uploaded','import.validation_failed','import.succeeded','import.cancelled',
  'dataset.updated','dataset.archived','dataset.deleted',
  'analysis.created','analysis.updated','analysis.deleted','analysis.copied',
  'dashboard.created','dashboard.updated','dashboard.deleted','dashboard.copied',
  'sharing.granted','sharing.revoked','sharing.authorized','sharing.authorization_revoked'
));
