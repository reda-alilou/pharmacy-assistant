CREATE TABLE platform.analyses (
  id uuid PRIMARY KEY,
  owner_id uuid NOT NULL REFERENCES platform.users(id),
  title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 160),
  description text NOT NULL DEFAULT '' CHECK (length(description) <= 4000),
  definition jsonb NOT NULL CHECK (jsonb_typeof(definition)='object' AND definition->>'algorithm'='cp3-v1'),
  revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX analyses_owner_idx ON platform.analyses(owner_id,updated_at DESC,id);
CREATE TABLE platform.analysis_sources (
  analysis_id uuid NOT NULL REFERENCES platform.analyses(id) ON DELETE CASCADE,
  dataset_id uuid NOT NULL,
  version_id uuid NOT NULL,
  PRIMARY KEY(analysis_id,version_id),
  FOREIGN KEY(dataset_id,version_id) REFERENCES platform.dataset_versions(dataset_id,id)
);
CREATE INDEX analysis_sources_dataset_idx ON platform.analysis_sources(dataset_id);
ALTER TABLE platform.activity DROP CONSTRAINT activity_resource_kind_check;
ALTER TABLE platform.activity ADD CONSTRAINT activity_resource_kind_check CHECK (resource_kind IN ('account','dataset','import','analysis'));
ALTER TABLE platform.activity DROP CONSTRAINT activity_action_check;
ALTER TABLE platform.activity ADD CONSTRAINT activity_action_check CHECK (action IN (
  'account.registered','account.provisioned','account.updated','account.password_changed','account.permissions_changed',
  'import.uploaded','import.validation_failed','import.succeeded','import.cancelled',
  'dataset.updated','dataset.archived','dataset.deleted',
  'analysis.created','analysis.updated','analysis.deleted'
));
