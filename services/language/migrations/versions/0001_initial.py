"""Initial language schema. Frozen DDL: do not import mutable runtime metadata."""

from alembic import op

revision = "language_0001"
down_revision = None
branch_labels = None
depends_on = None

STATEMENTS = (
    """CREATE TABLE language.evaluation_budgets (
    id TEXT NOT NULL,
    evaluation_id TEXT NOT NULL,
    maximum BIGINT NOT NULL,
    used BIGINT NOT NULL,
    PRIMARY KEY (id),
    CHECK (maximum >= 0 AND used >= 0 AND used <= maximum)
)""",
    """CREATE INDEX ix_language_evaluation_budgets_evaluation_id ON language.evaluation_budgets (evaluation_id)""",
    """CREATE TABLE language.quota_imports (
    input_hash TEXT NOT NULL,
    source_path TEXT NOT NULL,
    imported_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (input_hash)
)""",
    """CREATE TABLE language.quota_state (
    scope TEXT NOT NULL,
    next_at TIMESTAMP WITH TIME ZONE NOT NULL,
    blocked_until TIMESTAMP WITH TIME ZONE NOT NULL,
    block_code TEXT,
    attempts BIGINT NOT NULL,
    PRIMARY KEY (scope),
    CHECK (attempts >= 0)
)""",
)


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    op.execute("DROP TABLE language.quota_state")
    op.execute("DROP TABLE language.quota_imports")
    op.execute("DROP TABLE language.evaluation_budgets")
