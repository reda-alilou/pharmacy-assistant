"""Explicit relational import and lossless reconstruction of existing API records."""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json

from sqlalchemy import func, insert, select, text

from pharmacy_assistant.core.catalog import MedicationCatalog
from pharmacy_assistant.core.models import Medication
from pharmacy_assistant.core.pharmacy_models import PharmacyRecord
from pharmacy_assistant.core.pharmacy_directory import PharmacyDirectory
from pharmacy_assistant.core.medication_normalization import NAME_ALIASES, CONFIRMATION_ALIASES, arabic_normalize
from pharmacy_assistant.core.storage import models as m


VERSION = "relational-v1"
IDENTITY = ("brand_name", "active_substance", "epi", "dosage", "form")
PRICE_FIELDS = {"ppv": "ppv_price_mad", "hospital": "hospital_price_mad", "pfht": "pfht_price_mad"}


def instant(value):
    if value is None:
        return None
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Source timestamps must include a timezone.")
    return result


def amount(value):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("Boolean values are not prices.")
    value = Decimal(str(value))
    if not value.is_finite() or value < 0 or value >= Decimal("10000000000") or value != value.quantize(Decimal(".01")):
        raise ValueError("Source price cannot be represented without loss.")
    return value


def alias_rows():
    rows, seen = [], {}
    for requires_confirmation, aliases in ((False, NAME_ALIASES), (True, CONFIRMATION_ALIASES)):
        for spelling, target in aliases.items():
            normalized = arabic_normalize(spelling)
            mapping = (target, requires_confirmation)
            if normalized in seen and seen[normalized] != mapping:
                raise ValueError("Conflicting reviewed aliases.")
            seen[normalized] = mapping
            rows.append(dict(spelling=spelling, normalized_key=normalized, target=target,
                             requires_confirmation=requires_confirmation))
    return rows


def batch_insert(connection, table, rows):
    for offset in range(0, len(rows), 500):
        connection.execute(insert(table), rows[offset:offset + 500])


def reconstruct(connection):
    groups = {r["id"]: dict(r) for r in connection.execute(select(m.medications)).mappings()}
    prices, observations, conflicts = defaultdict(dict), defaultdict(list), defaultdict(list)
    for r in connection.execute(select(m.presentation_prices)).mappings():
        prices[r["presentation_id"]][PRICE_FIELDS[r["kind"]]] = float(r["amount"]) if r["amount"] is not None else None
    for table, result in ((m.source_observations, observations), (m.data_conflicts, conflicts)):
        for row in connection.execute(select(table).order_by(table.c.presentation_id, table.c.position)).mappings():
            row = dict(row)
            identifier = row.pop("presentation_id")
            row.pop("position")
            row.pop("fetched_at", None)
            for key in ("ppv_price_mad", "hospital_price_mad"):
                if key in row and row[key] is not None:
                    row[key] = float(row[key])
            result[identifier].append(row)
    records = []
    for row in connection.execute(select(m.presentations).order_by(m.presentations.c.source_order)).mappings():
        row = dict(row)
        identifier = row["source_record_id"]
        group = groups[row.pop("medication_id")]
        row.pop("source_order")
        row.pop("fetched_at")
        if set(prices[identifier]) != set(PRICE_FIELDS.values()):
            raise ValueError("Presentation prices are incomplete.")
        records.append(Medication.model_validate({**row, **{k: group[k] for k in IDENTITY},
            **prices[identifier], "source_observations": observations[identifier], "data_conflicts": conflicts[identifier]}))
    directory = []
    for row in connection.execute(select(m.pharmacies).order_by(m.pharmacies.c.source_order)).mappings():
        row = dict(row)
        row.pop("source_order")
        row.pop("fetched_at")
        directory.append(PharmacyRecord.model_validate(row))
    stored_aliases = [dict(r) for r in connection.execute(select(m.medication_aliases)).mappings()]
    if sorted(stored_aliases, key=lambda r: r["spelling"]) != sorted(alias_rows(), key=lambda r: r["spelling"]):
        raise ValueError("Stored aliases differ from the reviewed normalization version.")
    return records, directory


def load_catalogue(engine):
    with engine.connect() as connection:
        records, directory = reconstruct(connection)
    return MedicationCatalog(records, "postgresql:core.presentations"), PharmacyDirectory(directory)


def import_catalogue(engine, medication_path, pharmacy_path):
    records = MedicationCatalog.from_path(medication_path).records
    if not pharmacy_path.is_file():
        raise ValueError("The explicit pharmacy import input is missing.")
    directory = PharmacyDirectory.from_path(pharmacy_path).records
    inputs = {kind: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
              for kind, path in (("medications", medication_path), ("pharmacies", pharmacy_path))}
    aliases = alias_rows()
    signature = hashlib.sha256(json.dumps([VERSION, {key: value["sha256"] for key, value in inputs.items()}, aliases],
                                         sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    expected = [r.model_dump(mode="json") for r in records]
    expected_pharmacies = [r.model_dump(mode="json") for r in directory]
    with engine.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(719942001)"))
        receipt = db.execute(select(m.import_runs).where(m.import_runs.c.id == signature)).mappings().first()
        if receipt:
            restored, pharmacies = reconstruct(db)
            if [r.model_dump(mode="json") for r in restored] != expected or [r.model_dump(mode="json") for r in pharmacies] != expected_pharmacies:
                raise ValueError("Stored data changed since this import; refusing to overwrite it.")
            return {**receipt["counts"], "repeated": True}
        if db.scalar(select(func.count()).select_from(m.presentations)) or db.scalar(select(func.count()).select_from(m.pharmacies)):
            raise ValueError("Database already contains different inputs. An explicit update migration is required.")
        batch_insert(db, m.sources, [{"id": value} for value in ("AMMPS", "medicament.ma", "saydalia.ma")])
        group_ids, groups, presentations, prices, observations, conflicts = {}, [], [], [], [], []
        for order, record in enumerate(expected):
            row = dict(record)
            identity = tuple(row.pop(k) for k in IDENTITY)
            if identity not in group_ids:
                group_ids[identity] = len(group_ids) + 1
                groups.append(dict(id=group_ids[identity], **dict(zip(IDENTITY, identity))))
            identifier = row["source_record_id"]
            for kind, key in PRICE_FIELDS.items():
                prices.append(dict(presentation_id=identifier, kind=kind, amount=amount(row.pop(key))))
            for position, observation in enumerate(row.pop("source_observations")):
                observations.append({**observation, "presentation_id": identifier, "position": position,
                    "fetched_at": instant(observation["fetched_at_utc"]),
                    "ppv_price_mad": amount(observation["ppv_price_mad"]),
                    "hospital_price_mad": amount(observation["hospital_price_mad"])})
            for position, conflict in enumerate(row.pop("data_conflicts")):
                conflicts.append({**conflict, "presentation_id": identifier, "position": position})
            presentations.append({**row, "medication_id": group_ids[identity], "source_order": order,
                                  "fetched_at": instant(row["source_fetched_at_utc"])})
        for table, values in ((m.medications, groups), (m.presentations, presentations),
                              (m.presentation_prices, prices), (m.source_observations, observations),
                              (m.data_conflicts, conflicts), (m.medication_aliases, aliases)):
            batch_insert(db, table, values)
        db.execute(text("SELECT setval(pg_get_serial_sequence('core.medications', 'id'), :maximum)"), {"maximum": len(groups)})
        batch_insert(db, m.pharmacies, [{**r, "source_order": order, "fetched_at": instant(r["fetched_at_utc"])}
                                       for order, r in enumerate(expected_pharmacies)])
        restored, pharmacies = reconstruct(db)
        if [r.model_dump(mode="json") for r in restored] != expected or [r.model_dump(mode="json") for r in pharmacies] != expected_pharmacies:
            raise ValueError("Relational round-trip changed source data; transaction rolled back.")
        counts = dict(medications=len(groups), presentations=len(records), pharmacies=len(directory),
                      source_observations=len(observations), data_conflicts=len(conflicts), aliases=len(aliases))
        db.execute(insert(m.import_runs).values(id=signature, importer_version=VERSION, inputs=inputs,
                                              counts=counts, completed_at=datetime.now(timezone.utc)))
    return {**counts, "repeated": False}
