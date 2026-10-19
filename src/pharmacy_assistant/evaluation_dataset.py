"""Versioned annotations and freeze validation; no inference or prompt tuning."""

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pharmacy_assistant.catalog import DATASET, MedicationCatalog
from pharmacy_assistant.config import ROOT
from pharmacy_assistant.nlu_models import Interpretation, InterpretationRequest, normalize_span


DATA_DIRECTORY = ROOT / "data/evaluation/baseline_v1"
GROUPS = ("fr", "ar", "darija", "mixed")


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MedicationExpectation(Contract):
    mention_index: int = Field(ge=0, le=9)
    outcome: Literal["resolved", "clarify", "confirm_spelling", "not_found"]
    record_ids: list[str] = Field(default_factory=list)
    active_substance: str | None = None
    minimum_candidates: int = Field(default=0, ge=0)


class OutcomeExpectation(Contract):
    medications: list[MedicationExpectation] = Field(default_factory=list)
    pharmacy_status: Literal["matches", "not_found", "outside_coverage"] | None = None
    pharmacy_ids: list[str] = Field(default_factory=list)
    stock_unknown: bool = False
    no_medication_facts: bool = False
    missing_price: bool = False
    quantity_total_mad: float | None = Field(default=None, ge=0)
    require_clarification: bool = False


class ContextTurn(Contract):
    text: str
    interpretation: Interpretation

    @model_validator(mode="after")
    def evidence(self):
        InterpretationRequest(text=self.text)
        self.interpretation.validate_evidence(self.text)
        return self


class EvaluationExample(ContextTurn):
    id: str
    split: Literal["development", "held_out"]
    group: Literal["fr", "ar", "darija", "mixed"]
    kind: Literal["single_turn", "conversation_turn"] = "single_turn"
    tags: list[str] = Field(min_length=1)
    context: list[ContextTurn] = Field(default_factory=list)
    expected: OutcomeExpectation
    rationale: str = Field(min_length=10)
    alternatives: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def annotation_consistency(self):
        if bool(self.context) != (self.kind == "conversation_turn"):
            raise ValueError("Conversation cases require context; single-turn cases cannot have context")
        if self.group != self.interpretation.language:
            raise ValueError("Group and annotated language disagree")
        indices = [m.mention_index for m in self.expected.medications]
        if len(indices) != len(set(indices)):
            raise ValueError("Duplicate expected medication mention")
        for index in indices:
            if index >= len(self.interpretation.entities.medications):
                raise ValueError("Expected mention index has no annotation")
        for path, values in self.alternatives.items():
            if path.startswith("medications."):
                _, index, field = path.split(".")
                current = getattr(self.interpretation.entities.medications[int(index)], field)
            else:
                current = getattr(self.interpretation.entities, path)
            if current is None or not values or any(normalize_span(v) not in normalize_span(self.text) for v in values):
                raise ValueError("Alternate spans require a non-null annotated slot and message evidence")
        return self


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_examples(split: str = "development", directory: Path = DATA_DIRECTORY) -> list[EvaluationExample]:
    if split not in {"development", "held_out"}:
        raise ValueError("Unknown evaluation split")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    path = directory / f"{split}.json"
    if sha256(path) != manifest["files"][path.name]["sha256"]:
        raise ValueError("Frozen annotations changed; create a new dataset version")
    cases = [EvaluationExample.model_validate(row) for row in json.loads(path.read_text(encoding="utf-8"))]
    if len(cases) != 40 or Counter(c.group for c in cases) != {g: 10 for g in GROUPS}:
        raise ValueError("Each split must contain 40 cases, 10 per language group")
    if any(case.split != split for case in cases) or len({c.id for c in cases}) != len(cases):
        raise ValueError("Wrong split or duplicate IDs")
    return cases


def validate_dataset(directory: Path = DATA_DIRECTORY, *, catalog_path: Path = DATASET) -> dict:
    # Held-out data is read only for schema/evidence/freeze checks, never run
    # through the model or backend in this development checkpoint.
    development = load_examples("development", directory)
    held_out = load_examples("held_out", directory)
    all_cases = development + held_out
    if len({c.id for c in all_cases}) != 80:
        raise ValueError("Example IDs overlap across splits")
    if len({normalize_span(c.text) for c in all_cases}) != 80:
        raise ValueError("Duplicate messages across examples")
    catalog = MedicationCatalog.from_path(catalog_path)
    for case in all_cases:
        for expectation in case.expected.medications:
            if any(catalog.get(identifier) is None for identifier in expectation.record_ids):
                raise ValueError(f"Unknown annotated record ID in {case.id}")
            if expectation.outcome == "resolved" and len(expectation.record_ids) != 1:
                raise ValueError("Resolved expectations require one reviewed catalogue ID")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    return {"examples": 80, "development": len(development), "held_out": len(held_out),
            "by_split_and_group": {split: dict(Counter(c.group for c in all_cases if c.split == split))
                                   for split in ("development", "held_out")},
            "kinds": dict(Counter(c.kind for c in all_cases)),
            "catalogue_matches_annotation_snapshot": sha256(catalog_path) == manifest["catalogue_sha256"],
            "held_out_execution": "not_run", "annotation_provenance": manifest["annotation_provenance"]}


def main():
    print(json.dumps(validate_dataset(), indent=2))


if __name__ == "__main__":
    main()
