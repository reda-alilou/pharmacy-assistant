"""SQLAlchemy table models, separate from Pydantic public API contracts."""

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Column, DateTime,
                        Float, ForeignKey, Index, Integer, MetaData, Numeric, Table, Text,
                        UniqueConstraint, Uuid, func)
from sqlalchemy.dialects.postgresql import JSONB


metadata = MetaData(schema="core")


def text_column(name, *, nullable=False, **kwargs):
    return Column(name, Text, nullable=nullable, **kwargs)


def money_column(name):
    return Column(name, Numeric(12, 2), CheckConstraint(
        f"{name} >= 0 AND {name} NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)"), nullable=True)


def timestamp(name, *, nullable=False):
    return Column(name, DateTime(timezone=True), nullable=nullable)


sources = Table("sources", metadata, text_column("id", primary_key=True))
medications = Table("medications", metadata,
    Column("id", BigInteger, primary_key=True),
    *(Column(key, Text(collation="C"), nullable=False) for key in
      ("brand_name", "active_substance", "epi", "dosage", "form")),
    UniqueConstraint("brand_name", "active_substance", "epi", "dosage", "form"),
    CheckConstraint("btrim(brand_name) <> '' AND btrim(active_substance) <> '' AND btrim(epi) <> '' AND btrim(dosage) <> '' AND btrim(form) <> ''"))
Index("ix_medications_brand", medications.c.brand_name)
Index("ix_medications_substance", medications.c.active_substance)

presentations = Table("presentations", metadata,
    text_column("source_record_id", primary_key=True),
    Column("medication_id", ForeignKey("core.medications.id"), nullable=False, index=True),
    Column("source", ForeignKey("core.sources.id"), nullable=False),
    text_column("presentation"), text_column("commercialization_status"),
    Column("source_page", Integer, nullable=False), text_column("source_url"),
    *(text_column(key, nullable=True) for key in
      ("authorization_status", "therapeutic_class", "pp_gn_raw", "vat_raw",
       "rcp_naf_reference", "detailed_source_url", "source_fetched_at_utc", "atc_code", "reimbursement_status")),
    timestamp("fetched_at", nullable=True), Column("source_order", Integer, nullable=False, unique=True),
    CheckConstraint("source_record_id ~ '^[0-9]+$' AND source = 'AMMPS' AND source_page > 0"),
    CheckConstraint("btrim(presentation) <> '' AND btrim(commercialization_status) <> ''"),
    CheckConstraint("reimbursement_status IS NULL OR reimbursement_status IN ('yes','no')"))

presentation_prices = Table("presentation_prices", metadata,
    Column("presentation_id", ForeignKey("core.presentations.source_record_id", ondelete="CASCADE"), primary_key=True),
    text_column("kind", primary_key=True), money_column("amount"),
    CheckConstraint("kind IN ('ppv', 'hospital', 'pfht')"))

source_observations = Table("source_observations", metadata,
    Column("presentation_id", ForeignKey("core.presentations.source_record_id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("source", ForeignKey("core.sources.id"), nullable=False),
    text_column("source_record_id"), text_column("source_url"), text_column("fetched_at_utc"), timestamp("fetched_at"),
    *(text_column(key, nullable=True) for key in ("source_updated_at_raw", "atc_code", "reimbursement_raw", "commercialization_status")),
    money_column("ppv_price_mad"), money_column("hospital_price_mad"),
    UniqueConstraint("presentation_id", "source", "source_record_id", "fetched_at_utc"),
    CheckConstraint("position >= 0 AND source IN ('medicament.ma', 'saydalia.ma')"))

data_conflicts = Table("data_conflicts", metadata,
    Column("presentation_id", ForeignKey("core.presentations.source_record_id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, primary_key=True), text_column("field"),
    Column("reference_value", JSONB(none_as_null=False), nullable=False),
    Column("observed_value", JSONB(none_as_null=False), nullable=False),
    Column("source", ForeignKey("core.sources.id"), nullable=False), text_column("source_url"),
    CheckConstraint("position >= 0 AND source IN ('medicament.ma', 'saydalia.ma')"),
    CheckConstraint("jsonb_typeof(reference_value) IN ('string','number','boolean','null') AND jsonb_typeof(observed_value) IN ('string','number','boolean','null')"))

medication_aliases = Table("medication_aliases", metadata,
    text_column("spelling", primary_key=True), text_column("normalized_key", index=True),
    text_column("target"), Column("requires_confirmation", Boolean, nullable=False))

pharmacies = Table("pharmacies", metadata,
    text_column("pharmacy_id", primary_key=True), text_column("name", index=True), text_column("city"),
    text_column("address", nullable=True), text_column("phone", nullable=True),
    Column("latitude", Float(53), nullable=False), Column("longitude", Float(53), nullable=False),
    text_column("opening_information", nullable=True), Column("source", ForeignKey("core.sources.id"), nullable=False),
    text_column("source_url"), text_column("source_request_url"), text_column("fetched_at_utc"), timestamp("fetched_at"),
    text_column("directory_scope"), Column("source_order", Integer, nullable=False, unique=True),
    CheckConstraint("latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180"),
    CheckConstraint("pharmacy_id ~ '^saydalia:[0-9]+$' AND city = 'Rabat' AND btrim(name) <> ''"))

import_runs = Table("import_runs", metadata,
    text_column("id", primary_key=True), text_column("importer_version"),
    Column("inputs", JSONB, nullable=False), Column("counts", JSONB, nullable=False),
    timestamp("completed_at"))

conversations = Table("conversations", metadata,
    Column("id", Uuid, primary_key=True), timestamp("created_at"), timestamp("last_success_at", nullable=True),
    timestamp("expires_at"), Column("revision", BigInteger, nullable=False, server_default="0"),
    Column("next_sequence", BigInteger, nullable=False, server_default="0"),
    CheckConstraint("revision >= 0 AND next_sequence >= 0 AND expires_at >= created_at"))
Index("ix_conversations_expiry", conversations.c.expires_at)

conversation_messages = Table("conversation_messages", metadata,
    Column("id", Uuid, primary_key=True),
    Column("conversation_id", ForeignKey("core.conversations.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("sequence", BigInteger, nullable=False), text_column("role"), text_column("outcome"),
    text_column("text", nullable=True), timestamp("created_at"),
    text_column("request_key", nullable=True), text_column("request_fingerprint", nullable=True),
    Column("payload", JSONB, nullable=True),
    UniqueConstraint("conversation_id", "sequence"), UniqueConstraint("conversation_id", "request_key"),
    CheckConstraint("role IN ('user','assistant') AND outcome IN ('pending','answered','failed') AND sequence >= 0"))

conversation_states = Table("conversation_states", metadata,
    text_column("token_hash", primary_key=True),
    Column("conversation_id", ForeignKey("core.conversations.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("revision", BigInteger, nullable=False), Column("payload", JSONB, nullable=False), timestamp("created_at"),
    CheckConstraint("length(token_hash) = 64 AND revision >= 0"))

pending_choices = Table("pending_choices", metadata,
    text_column("token_hash", primary_key=True),
    Column("conversation_id", ForeignKey("core.conversations.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("revision", BigInteger, nullable=False), Column("payload", JSONB, nullable=False), timestamp("created_at"),
    CheckConstraint("length(token_hash) = 64 AND revision >= 0"))
