"""Bounded conversation snapshots and conservative, provider-independent merging.

Raw extraction always describes the current message alone. Inherited values live
in a separate effective interpretation and carry explicit field paths.
"""

from dataclasses import dataclass
import re

from pharmacy_core.conversation.answers import MEDICATION_INTENTS, PHARMACY_INTENTS
from pharmacy_core.medications.catalog import normalize
from pharmacy_core.conversation.models import ContextReferenceOption, ConversationContext, MedicationResult
from pharmacy_core.medications.normalization import arabic_normalize, lookup_name, strength_key, form_key
from pharmacy_contracts.interpretation import Interpretation, InterpretationResponse, MedicationMention


@dataclass
class ConversationSnapshot:
    expires: float
    effective: Interpretation
    anchors: list[MedicationMention]
    results: list[MedicationResult]
    pending_fragment: InterpretationResponse | None = None


def anchors_for(results):
    anchors = []
    for result in results:
        values = {**result.mention.model_dump(), **result.applied_refinements}
        if result.medication is not None:
            record = result.medication
            # A selected/resolved record, rather than a rejected original filter,
            # is the product remembered on the next turn. Do not invent unknowns.
            values.update(name=record.brand_name, strength=record.dosage, form=record.form,
                          presentation=record.presentation)
            for field in ("strength", "form", "presentation"):
                if len(values[field]) > 200 or normalize(values[field]) in {"", "-", "na", "n/a", "non renseigne"}:
                    values[field] = None
        values.pop("brand_name", None)
        anchors.append(MedicationMention.model_validate(values))
    return anchors


ORDINALS = {
    "le premier": 0, "la premiere": 0, "le premier choix": 0, "the first one": 0,
    "le deuxieme": 1, "la deuxieme": 1, "le second": 1, "la seconde": 1, "the second one": 1,
    "le troisieme": 2, "la troisieme": 2, "the third one": 2,
    "le quatrieme": 3, "la quatrieme": 3, "the fourth one": 3,
    "le cinquieme": 4, "la cinquieme": 4, "the fifth one": 4,
    "الاولى": 0, "الاول": 0, "الثانية": 1, "الثاني": 1, "التانية": 1, "التاني": 1,
    "الثالثة": 2, "الثالث": 2, "لولة": 0, "لول": 0, "تانية": 1,
    "louwla": 0, "lowla": 0, "taniya": 1, "tanya": 1, "ttaniya": 1,
}


def ordinal_index(text):
    # Only complete reviewed phrases qualify, never substrings of clinical text.
    value = arabic_normalize(text).strip(" .!?؟،")
    value = re.sub(r"(?:,?\s+(?:merci|svp|s'il vous plait|s'il te plait|3afak|عافاك|من فضلك))$", "", value)
    return ORDINALS.get(value)


def same_name(first, second):
    return first is not None and second is not None and normalize(lookup_name(first)) == normalize(lookup_name(second))


def combine_mention(current, anchor, inherited, index):
    values = current.model_dump()
    # A change of strength/form can invalidate the old presentation. A new form
    # also clears the previous strength instead of assuming it exists in that form.
    strength_changed = current.strength is not None and strength_key(current.strength) != strength_key(anchor.strength or "")
    form_changed = current.form is not None and form_key(current.form) != form_key(anchor.form or "")
    for field, old in anchor.model_dump().items():
        if field == "presentation" and (strength_changed or form_changed):
            continue
        if field == "strength" and form_changed and current.strength is None:
            continue
        if field == "form" and strength_changed and current.form is None:
            continue
        if values[field] is None and old is not None:
            values[field] = old
            inherited.append(f"medications.{index}.{field}")
    return MedicationMention.model_validate(values)


def merge_context(raw: Interpretation, previous: ConversationSnapshot | None, *, reference_index=None,
                  ordinal=None):
    effective = raw.model_copy(deep=True)
    context = ConversationContext(effective_interpretation=effective)
    pins = {}
    if previous is None or "unsupported" in raw.intents and ordinal is None:
        return context, pins
    # A definite container reference alongside a stated presentation selects the
    # package; it does not supply an order count. Preserve the original model
    # extraction and record this bounded correction separately from inheritance.
    mentions = effective.entities.medications
    if previous.anchors and len(mentions) == 1 and mentions[0].name is None and mentions[0].presentation is not None:
        current = mentions[0]
        if current.quantity is not None and arabic_normalize(current.quantity) in {
            "lboita", "l3elba", "la boite", "le flacon", "العلبة", "القارورة", "القنينة",
        }:
            current.quantity = None
            context.normalized_fields.append("medications.0.quantity")
            if effective.intents == ["medication_request"]:
                effective.intents = ["medication_information"]
                context.normalized_fields.append("intents")
    intents = set(effective.intents)
    old_intents = set(previous.effective.intents)
    mentions = effective.entities.medications
    if ordinal is not None and old_intents & MEDICATION_INTENTS:
        if len(previous.results) == 1 and previous.results[0].candidates and (
            previous.results[0].candidate_count <= 5 or previous.results[0].clarification is None or
            previous.results[0].clarification.field is None
        ) and ordinal < len(previous.results[0].candidates):
            result = previous.results[0]
            record = result.candidates[ordinal]
            effective.entities.medications = [result.mention.model_copy(deep=True)]
            effective.intents = [i for i in previous.effective.intents if i in MEDICATION_INTENTS]
            context.action = "ordinal_selection"
            context.inherited_fields = ["intents", "medications.0"]
            pins[0] = record
            return context, pins
        # An ordinal must not silently map to one of several medication lists.
        context.needs_reference = True
        context.action = "followup"
        return context, pins
    if intents & MEDICATION_INTENTS and old_intents & MEDICATION_INTENTS and previous.anchors:
        unnamed = [i for i, medication in enumerate(mentions) if medication.name is None]
        # Empty price/availability requests refer to the sole preceding medicine.
        if not mentions:
            mentions.append(MedicationMention(name=None, strength=None, quantity=None, form=None, presentation=None))
            unnamed = [0]
        if unnamed and len(mentions) == 1 and effective.intents == ["medication_information"] and any(
            getattr(mentions[0], field) is not None for field in ("strength", "quantity", "form", "presentation")
        ):
            effective.intents = [i for i in previous.effective.intents if i in MEDICATION_INTENTS]
            context.inherited_fields.append("intents")
        if unnamed and (len(previous.anchors) != 1 or len(mentions) != 1) and reference_index is None:
            context.needs_reference = True
            context.action = "followup"
            context.reference_options = [ContextReferenceOption(mention_index=i, medication=anchor)
                                         for i, anchor in enumerate(previous.anchors)] if len(mentions) == 1 else []
            return context, pins
        for index, medication in enumerate(mentions):
            matches = [i for i, anchor in enumerate(previous.anchors) if same_name(medication.name, anchor.name)]
            selected = reference_index if medication.name is None and reference_index is not None else (
                0 if medication.name is None and len(previous.anchors) == 1 else matches[0] if len(matches) == 1 else None)
            if selected is None:
                continue  # A new named product starts without inherited filters.
            anchor = previous.anchors[selected]
            effective.entities.medications[index] = combine_mention(medication, anchor, context.inherited_fields, index)
            previous_result = previous.results[selected]
            if previous_result.medication is not None:
                from pharmacy_core.medications.matching import passes
                if passes(previous_result.medication, effective.entities.medications[index]):
                    pins[index] = previous_result.medication
        context.action = "reference_choice" if reference_index is not None else "followup" if context.inherited_fields else "independent"
    elif intents & PHARMACY_INTENTS and old_intents & PHARMACY_INTENTS:
        entities, old = effective.entities, previous.effective.entities
        city_changed = entities.city is not None and not same_name(entities.city, old.city)
        pharmacy_changed = entities.pharmacy is not None and not same_name(entities.pharmacy, old.pharmacy)
        for field in ("city", "area", "pharmacy"):
            if (city_changed and field != "city") or (pharmacy_changed and field == "area"):
                continue
            if getattr(entities, field) is None and getattr(old, field) is not None:
                setattr(entities, field, getattr(old, field))
                context.inherited_fields.append(field)
        if context.inherited_fields:
            context.action = "followup"
    return context, pins
