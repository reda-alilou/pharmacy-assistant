"""One inference call, local retrieval, and templated answers.

Continuation state is opaque, bounded, memory-only, and expires after 15 minutes.
Only records and refinement options actually offered for a mention may be
selected on a follow-up.
"""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
import time

from pharmacy_assistant.core.errors import ChatError

from pharmacy_assistant.core.answer_templates import MEDICATION_INTENTS, PHARMACY_INTENTS, render_answer
from pharmacy_assistant.core.catalog import MedicationCatalog
from pharmacy_assistant.core.chat_models import ChatRequest, ChatResponse, ConversationContext, MedicationResult, SourceInfo
from pharmacy_assistant.core.conversation import ConversationSnapshot, anchors_for, merge_context, ordinal_index
from pharmacy_assistant.contracts.interpreter import Interpreter
from pharmacy_assistant.contracts.nlu_models import InterpretationRequest, InterpretationResponse
from pharmacy_assistant.core.pharmacy_directory import PharmacyDirectory
from pharmacy_assistant.core.pricing import apply_pricing
from pharmacy_assistant.core.resolution import ResolutionState, mismatches, refine_resolution, resolve_with_state


@dataclass
class PendingChoice:
    expires: float
    interpretation: InterpretationResponse
    results: list[MedicationResult]
    resolution_states: dict[int, ResolutionState]
    context: ConversationContext


class ChatService:
    def __init__(self, catalog: MedicationCatalog, interpreter: Interpreter,
                 directory: PharmacyDirectory, *, ttl_seconds: float = 900, capacity: int = 128):
        self.catalog = catalog
        self.interpreter = interpreter
        self.directory = directory
        self.ttl_seconds = ttl_seconds
        self.capacity = capacity
        self.pending: OrderedDict[str, PendingChoice] = OrderedDict()
        self.sessions: OrderedDict[str, ConversationSnapshot] = OrderedDict()

    def prune(self):
        now = time.monotonic()
        for token in list(self.pending):
            if self.pending[token].expires <= now:
                del self.pending[token]
        for token in list(self.sessions):
            if self.sessions[token].expires <= now:
                del self.sessions[token]

    async def respond(self, request: ChatRequest) -> ChatResponse:
        self.prune()
        previous = None
        if request.session_id is not None:
            previous = self.sessions.get(request.session_id)
            if previous is None:
                raise ChatError("session_expired", "Conversation expired or server restarted. Start a new conversation with a complete question.")
        inference_performed = request.continuation_id is None and request.reference_index is None
        if request.continuation_id is None:
            if request.reference_index is not None:
                if previous.pending_fragment is None or request.reference_index >= len(previous.anchors):
                    raise ChatError("invalid_reference", "Choose an offered medication reference.")
                interpreted = previous.pending_fragment.model_copy(deep=True)
            else:
                interpreted = await self.interpreter.interpret(InterpretationRequest(text=request.text))
            context, pins = merge_context(interpreted.interpretation, previous,
                reference_index=request.reference_index, ordinal=ordinal_index(request.text or ""))
            effective = context.effective_interpretation
            outcomes = [resolve_with_state(self.catalog, mention, index) for index, mention
                        in enumerate(effective.entities.medications)] if (
                           not context.needs_reference and set(effective.intents) & MEDICATION_INTENTS
                       ) else []
            for index, record in pins.items():
                if not context.needs_reference:
                    outcomes[index] = (MedicationResult(mention_index=index, mention=effective.entities.medications[index],
                        status="resolved", match_method="user_selection" if context.action == "ordinal_selection" else "context_record", medication=record,
                        conflicting_filters=mismatches(record, effective.entities.medications[index])), None)
            results = [result for result, _ in outcomes]
            states = {index: state for index, (_, state) in enumerate(outcomes) if state is not None}
        else:
            pending = self.pending.get(request.continuation_id)
            if pending is None:
                raise ChatError("clarification_expired", "Clarification expired or server restarted. Send the original text again.")
            interpreted = pending.interpretation.model_copy(deep=True)
            context = pending.context.model_copy(deep=True)
            results = [result.model_copy(deep=True) for result in pending.results]
            states = dict(pending.resolution_states)
            for selection in request.selections:
                if selection.mention_index >= len(results):
                    raise ChatError("invalid_selection", "Unknown medication mention.")
                result = results[selection.mention_index]
                allowed = {record.source_record_id for record in result.candidates}
                if selection.record_id not in allowed:
                    raise ChatError("invalid_selection", "Choose a record offered for this medication mention.")
                results[selection.mention_index] = MedicationResult(
                    mention_index=result.mention_index, mention=result.mention, status="resolved",
                    match_method="user_selection", medication=self.catalog.get(selection.record_id),
                    name_alias=result.name_alias, applied_refinements=result.applied_refinements,
                    conflicting_filters=mismatches(self.catalog.get(selection.record_id), result.mention),
                )
                states.pop(selection.mention_index, None)
            for refinement in request.refinements:
                index = refinement.mention_index
                if index >= len(results) or index not in states:
                    raise ChatError("invalid_refinement", "Unknown or already resolved medication mention.")
                try:
                    results[index], state = refine_resolution(self.catalog, states[index], results[index],
                                                              refinement.field, refinement.value)
                except ValueError:
                    raise ChatError("invalid_refinement", "Choose an option offered for this medication mention.") from None
                if state is None:
                    states.pop(index, None)
                else:
                    states[index] = state
        interpretation = context.effective_interpretation
        order_pricing = apply_pricing(results)
        intents = set(interpretation.intents)
        pharmacy = self.directory.search(interpretation.entities) if intents & PHARMACY_INTENTS else None
        needs_clarification = context.needs_reference or any(r.status != "resolved" for r in results) or (
            not results and bool(intents & MEDICATION_INTENTS)
        ) or any(r.pricing.status == "needs_quantity_clarification" for r in results) or (
            pharmacy is not None and pharmacy.status == "ambiguous"
        )
        token, expires_at = None, None
        if states:
            while len(self.pending) >= self.capacity:
                self.pending.popitem(last=False)
            token = secrets.token_urlsafe(32)
            self.pending[token] = PendingChoice(time.monotonic() + self.ttl_seconds,
                                               interpreted.model_copy(deep=True),
                                               [r.model_copy(deep=True) for r in results], dict(states), context.model_copy(deep=True))
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)).isoformat()
        while len(self.sessions) >= self.capacity:
            self.sessions.popitem(last=False)
        session_id = secrets.token_urlsafe(32)
        session_expires = (datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)).isoformat()
        self.sessions[session_id] = ConversationSnapshot(
            expires=time.monotonic() + self.ttl_seconds,
            effective=interpretation.model_copy(deep=True),
            anchors=([anchor.model_copy(deep=True) for anchor in previous.anchors] if context.needs_reference and previous
                     else anchors_for(results)),
            results=([result.model_copy(deep=True) for result in previous.results] if context.needs_reference and previous
                     else [result.model_copy(deep=True) for result in results]),
            pending_fragment=interpreted.model_copy(deep=True) if context.needs_reference and context.reference_options else None,
        )
        sources: dict[tuple[str, str, str | None], SourceInfo] = {}

        def add(source, url, fetched, record_id):
            key = (source, url, fetched)
            if key not in sources:
                sources[key] = SourceInfo(source=source, url=url, fetched_at_utc=fetched, record_ids=[])
            if record_id not in sources[key].record_ids:
                sources[key].record_ids.append(record_id)

        for result in results:
            for record in ([result.medication] if result.medication else result.candidates):
                add(record.source, record.source_url, record.source_fetched_at_utc, record.source_record_id)
                for observation in record.source_observations:
                    add(observation.source, observation.source_url, observation.fetched_at_utc, record.source_record_id)
        if pharmacy:
            for record in pharmacy.pharmacies:
                add(record.source, record.source_url, record.fetched_at_utc, record.pharmacy_id)
        return ChatResponse(
            status="needs_clarification" if needs_clarification else "answered",
            interpretation=interpreted.interpretation, medications=results, pharmacy=pharmacy,
            answer=render_answer(interpretation, results, pharmacy, needs_reference=context.needs_reference,
                                 order_pricing=order_pricing), sources=list(sources.values()),
            inference=interpreted.metadata, inference_performed=inference_performed,
            continuation_id=token, continuation_expires_at_utc=expires_at,
            session_id=session_id, session_expires_at_utc=session_expires, context=context,
            order_pricing=order_pricing,
        )
