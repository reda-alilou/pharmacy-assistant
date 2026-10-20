"""Language tables have no dependencies or foreign keys into the core schema."""

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, MetaData, Table, Text


metadata = MetaData(schema="language")
quota_state = Table("quota_state", metadata,
    Column("scope", Text, primary_key=True),
    Column("next_at", DateTime(timezone=True), nullable=False),
    Column("blocked_until", DateTime(timezone=True), nullable=False),
    Column("block_code", Text), Column("attempts", BigInteger, nullable=False),
    CheckConstraint("attempts >= 0"))
evaluation_budgets = Table("evaluation_budgets", metadata,
    Column("id", Text, primary_key=True), Column("evaluation_id", Text, nullable=False, index=True),
    Column("maximum", BigInteger, nullable=False), Column("used", BigInteger, nullable=False),
    CheckConstraint("maximum >= 0 AND used >= 0 AND used <= maximum"))
quota_imports = Table("quota_imports", metadata,
    Column("input_hash", Text, primary_key=True), Column("source_path", Text, nullable=False),
    Column("imported_at", DateTime(timezone=True), nullable=False))
