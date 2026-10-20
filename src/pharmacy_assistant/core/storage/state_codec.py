"""Versioned JSON state; no process clocks, Python pickle, or bearer secrets."""

import time

from pydantic import BaseModel, ConfigDict, Field

from pharmacy_assistant.core.chat import PendingChoice
from pharmacy_assistant.core.chat_models import ConversationContext, MedicationResult
from pharmacy_assistant.core.conversation import ConversationSnapshot
from pharmacy_assistant.core.resolution import ResolutionState
from pharmacy_assistant.contracts.nlu_models import Interpretation, InterpretationResponse, MedicationMention


class StatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1, le=1)
    effective: Interpretation
    anchors: list[MedicationMention]
    results: list[MedicationResult]
    pending_fragment: InterpretationResponse | None


class ResolutionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    mention: MedicationMention
    candidate_ids: list[str]
    method: str
    scores: dict[str, float]
    overrides: dict[str, str]
    name_alias: str | None
    confirm_identity: bool


class ChoicePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1, le=1)
    interpretation: InterpretationResponse
    results: list[MedicationResult]
    resolution_states: dict[int, ResolutionPayload]
    context: ConversationContext


def encode_state(state):
    return StatePayload(version=1, effective=state.effective, anchors=state.anchors,
                        results=state.results, pending_fragment=state.pending_fragment).model_dump(mode="json")


def decode_state(payload):
    value = StatePayload.model_validate(payload)
    return ConversationSnapshot(time.monotonic() + 1800, value.effective, value.anchors,
                                value.results, value.pending_fragment)


def encode_choice(choice):
    states = {index: ResolutionPayload(mention=value.mention, candidate_ids=list(value.candidate_ids),
              method=value.method, scores=value.scores, overrides=value.overrides,
              name_alias=value.name_alias, confirm_identity=value.confirm_identity)
              for index, value in choice.resolution_states.items()}
    return ChoicePayload(version=1, interpretation=choice.interpretation, results=choice.results,
                         resolution_states=states, context=choice.context).model_dump(mode="json")


def decode_choice(payload):
    # JSON object keys are strings; JSON-mode validation restores integer indexes.
    import json
    value = ChoicePayload.model_validate_json(json.dumps(payload))
    states = {index: ResolutionState(mention=row.mention, candidate_ids=tuple(row.candidate_ids),
              method=row.method, scores=row.scores, overrides=row.overrides, name_alias=row.name_alias,
              confirm_identity=row.confirm_identity) for index, row in value.resolution_states.items()}
    return PendingChoice(time.monotonic() + 1800, value.interpretation, value.results, states, value.context)
