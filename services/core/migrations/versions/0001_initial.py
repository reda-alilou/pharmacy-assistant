"""Initial core schema. Frozen DDL: do not import mutable runtime metadata."""

from alembic import op

revision = "core_0001"
down_revision = None
branch_labels = None
depends_on = None

STATEMENTS = (
    """CREATE TABLE core.conversations (
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_success_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revision BIGINT DEFAULT '0' NOT NULL,
    next_sequence BIGINT DEFAULT '0' NOT NULL,
    PRIMARY KEY (id),
    CHECK (revision >= 0 AND next_sequence >= 0 AND expires_at >= created_at)
)""",
    """CREATE INDEX ix_conversations_expiry ON core.conversations (expires_at)""",
    """CREATE TABLE core.import_runs (
    id TEXT NOT NULL,
    importer_version TEXT NOT NULL,
    inputs JSONB NOT NULL,
    counts JSONB NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id)
)""",
    """CREATE TABLE core.medication_aliases (
    spelling TEXT NOT NULL,
    normalized_key TEXT NOT NULL,
    target TEXT NOT NULL,
    requires_confirmation BOOLEAN NOT NULL,
    PRIMARY KEY (spelling)
)""",
    """CREATE INDEX ix_core_medication_aliases_normalized_key ON core.medication_aliases (normalized_key)""",
    """CREATE TABLE core.medications (
    id BIGSERIAL NOT NULL,
    brand_name TEXT COLLATE "C" NOT NULL,
    active_substance TEXT COLLATE "C" NOT NULL,
    epi TEXT COLLATE "C" NOT NULL,
    dosage TEXT COLLATE "C" NOT NULL,
    form TEXT COLLATE "C" NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (brand_name, active_substance, epi, dosage, form),
    CHECK (btrim(brand_name) <> '' AND btrim(active_substance) <> '' AND btrim(epi) <> '' AND btrim(dosage) <> '' AND btrim(form) <> '')
)""",
    """CREATE INDEX ix_medications_brand ON core.medications (brand_name)""",
    """CREATE INDEX ix_medications_substance ON core.medications (active_substance)""",
    """CREATE TABLE core.sources (
    id TEXT NOT NULL,
    PRIMARY KEY (id)
)""",
    """CREATE TABLE core.conversation_messages (
    id UUID NOT NULL,
    conversation_id UUID NOT NULL,
    sequence BIGINT NOT NULL,
    role TEXT NOT NULL,
    outcome TEXT NOT NULL,
    text TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    request_key TEXT,
    request_fingerprint TEXT,
    payload JSONB,
    PRIMARY KEY (id),
    UNIQUE (conversation_id, sequence),
    UNIQUE (conversation_id, request_key),
    CHECK (role IN ('user','assistant') AND outcome IN ('pending','answered','failed') AND sequence >= 0),
    FOREIGN KEY(conversation_id) REFERENCES core.conversations (id) ON DELETE CASCADE
)""",
    """CREATE INDEX ix_core_conversation_messages_conversation_id ON core.conversation_messages (conversation_id)""",
    """CREATE TABLE core.conversation_states (
    token_hash TEXT NOT NULL,
    conversation_id UUID NOT NULL,
    revision BIGINT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (token_hash),
    CHECK (length(token_hash) = 64 AND revision >= 0),
    FOREIGN KEY(conversation_id) REFERENCES core.conversations (id) ON DELETE CASCADE
)""",
    """CREATE INDEX ix_core_conversation_states_conversation_id ON core.conversation_states (conversation_id)""",
    """CREATE TABLE core.pending_choices (
    token_hash TEXT NOT NULL,
    conversation_id UUID NOT NULL,
    revision BIGINT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (token_hash),
    CHECK (length(token_hash) = 64 AND revision >= 0),
    FOREIGN KEY(conversation_id) REFERENCES core.conversations (id) ON DELETE CASCADE
)""",
    """CREATE INDEX ix_core_pending_choices_conversation_id ON core.pending_choices (conversation_id)""",
    """CREATE TABLE core.pharmacies (
    pharmacy_id TEXT NOT NULL,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    address TEXT,
    phone TEXT,
    latitude FLOAT(53) NOT NULL,
    longitude FLOAT(53) NOT NULL,
    opening_information TEXT,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_request_url TEXT NOT NULL,
    fetched_at_utc TEXT NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,
    directory_scope TEXT NOT NULL,
    source_order INTEGER NOT NULL,
    PRIMARY KEY (pharmacy_id),
    CHECK (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180),
    CHECK (pharmacy_id ~ '^saydalia:[0-9]+$' AND city = 'Rabat' AND btrim(name) <> ''),
    FOREIGN KEY(source) REFERENCES core.sources (id),
    UNIQUE (source_order)
)""",
    """CREATE INDEX ix_core_pharmacies_name ON core.pharmacies (name)""",
    """CREATE TABLE core.presentations (
    source_record_id TEXT NOT NULL,
    medication_id BIGINT NOT NULL,
    source TEXT NOT NULL,
    presentation TEXT NOT NULL,
    commercialization_status TEXT NOT NULL,
    source_page INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    authorization_status TEXT,
    therapeutic_class TEXT,
    pp_gn_raw TEXT,
    vat_raw TEXT,
    rcp_naf_reference TEXT,
    detailed_source_url TEXT,
    source_fetched_at_utc TEXT,
    atc_code TEXT,
    reimbursement_status TEXT,
    fetched_at TIMESTAMP WITH TIME ZONE,
    source_order INTEGER NOT NULL,
    PRIMARY KEY (source_record_id),
    CHECK (source_record_id ~ '^[0-9]+$' AND source = 'AMMPS' AND source_page > 0),
    CHECK (btrim(presentation) <> '' AND btrim(commercialization_status) <> ''),
    CHECK (reimbursement_status IS NULL OR reimbursement_status IN ('yes','no')),
    FOREIGN KEY(medication_id) REFERENCES core.medications (id),
    FOREIGN KEY(source) REFERENCES core.sources (id),
    UNIQUE (source_order)
)""",
    """CREATE INDEX ix_core_presentations_medication_id ON core.presentations (medication_id)""",
    """CREATE TABLE core.data_conflicts (
    presentation_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    field TEXT NOT NULL,
    reference_value JSONB NOT NULL,
    observed_value JSONB NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    PRIMARY KEY (presentation_id, position),
    CHECK (position >= 0 AND source IN ('medicament.ma', 'saydalia.ma')),
    CHECK (jsonb_typeof(reference_value) IN ('string','number','boolean','null') AND jsonb_typeof(observed_value) IN ('string','number','boolean','null')),
    FOREIGN KEY(presentation_id) REFERENCES core.presentations (source_record_id) ON DELETE CASCADE,
    FOREIGN KEY(source) REFERENCES core.sources (id)
)""",
    """CREATE TABLE core.presentation_prices (
    presentation_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    amount NUMERIC(12, 2) CHECK (amount >= 0 AND amount NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)),
    PRIMARY KEY (presentation_id, kind),
    CHECK (kind IN ('ppv', 'hospital', 'pfht')),
    FOREIGN KEY(presentation_id) REFERENCES core.presentations (source_record_id) ON DELETE CASCADE
)""",
    """CREATE TABLE core.source_observations (
    presentation_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    source TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    fetched_at_utc TEXT NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,
    source_updated_at_raw TEXT,
    atc_code TEXT,
    reimbursement_raw TEXT,
    commercialization_status TEXT,
    ppv_price_mad NUMERIC(12, 2) CHECK (ppv_price_mad >= 0 AND ppv_price_mad NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)),
    hospital_price_mad NUMERIC(12, 2) CHECK (hospital_price_mad >= 0 AND hospital_price_mad NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)),
    PRIMARY KEY (presentation_id, position),
    UNIQUE (presentation_id, source, source_record_id, fetched_at_utc),
    CHECK (position >= 0 AND source IN ('medicament.ma', 'saydalia.ma')),
    FOREIGN KEY(presentation_id) REFERENCES core.presentations (source_record_id) ON DELETE CASCADE,
    FOREIGN KEY(source) REFERENCES core.sources (id)
)""",
)


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    op.execute("DROP TABLE core.source_observations")
    op.execute("DROP TABLE core.presentation_prices")
    op.execute("DROP TABLE core.data_conflicts")
    op.execute("DROP TABLE core.presentations")
    op.execute("DROP TABLE core.pharmacies")
    op.execute("DROP TABLE core.pending_choices")
    op.execute("DROP TABLE core.conversation_states")
    op.execute("DROP TABLE core.conversation_messages")
    op.execute("DROP TABLE core.sources")
    op.execute("DROP TABLE core.medications")
    op.execute("DROP TABLE core.medication_aliases")
    op.execute("DROP TABLE core.import_runs")
    op.execute("DROP TABLE core.conversations")
