"""Conservative ranked identity matching and server-validated refinement."""

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from pharmacy_core.medications.catalog import MedicationCatalog, normalize
from pharmacy_core.conversation.models import ClarificationOption, MedicationClarification, MedicationResult
from pharmacy_core.medications.normalization import (
    NAME_ALIASES, FORM_GROUPS, alias_requires_confirmation, arabic_normalize,
    form_key, form_matches, lookup_name, presentation_matches, strength_key,
)
from pharmacy_contracts.interpretation import MedicationMention


MAX_RECORD_CHOICES = 5
FIELDS = ("strength", "form", "brand_name", "presentation")


@dataclass
class ResolutionState:
    mention: MedicationMention
    candidate_ids: tuple[str, ...]
    method: str
    scores: dict[str, float] = field(default_factory=dict)
    overrides: dict[str, str] = field(default_factory=dict)
    name_alias: str | None = None
    confirm_identity: bool = False


def mismatches(record, mention):
    return [field for field, passed in (
        ("strength", mention.strength is None or strength_key(record.dosage) == strength_key(mention.strength)),
        ("form", mention.form is None or form_matches(record.form, mention.form)),
        ("presentation", mention.presentation is None or presentation_matches(record.presentation, mention.presentation, record.form)),
    ) if not passed]


def passes(record, mention: MedicationMention) -> bool:
    return not mismatches(record, mention)


def field_value(record, field):
    return record.dosage if field == "strength" else getattr(record, field)


def field_key(value, field):
    return strength_key(value) if field == "strength" else form_key(value) if field == "form" else normalize(value)


def option_groups(catalog, ids, field):
    groups = {}
    for identifier in ids:
        value = field_value(catalog.by_id[identifier], field)
        key = field_key(value, field)
        if not key:
            continue
        if key not in groups:
            groups[key] = [value, []]
        groups[key][1].append(identifier)
    return sorted(groups.values(), key=lambda item: normalize(item[0]))


def identity_candidates(catalog, name):
    canonical = lookup_name(name)
    query = normalize(canonical)
    for field, method in (("brand_name", "exact_brand"), ("active_substance", "exact_substance")):
        ids = catalog.name_index.get((field, query))
        if ids:
            return list(ids), method, {identifier: 1.0 for identifier in ids}
    partial = {}
    if len(query) >= 3:
        for (_, term), ids in catalog.name_index.items():
            if query in term:
                for identifier in ids:
                    partial[identifier] = max(partial.get(identifier, 0), len(query) / len(term))
    if partial:
        return list(partial), "partial", partial
    if len(query) < 3:
        return [], "fuzzy", {}
    terms = []
    threshold = .85 if len(query) <= 4 else .75
    for (field, term), ids in catalog.name_index.items():
        if abs(len(term) - len(query)) > max(3, len(query) // 2):
            continue
        score = SequenceMatcher(None, query, term).ratio()
        if score >= threshold:
            terms.append((score, field, term, ids))
    scores = {}
    for score, _, _, ids in sorted(terms, key=lambda item: (-item[0], item[1], item[2]))[:5]:
        for identifier in ids:
            scores[identifier] = max(scores.get(identifier, 0), score)
    return list(scores), "fuzzy", scores


def build_resolution(catalog, state: ResolutionState, index: int, *, offset=0):
    mention = state.mention
    effective = mention.model_copy(update={k: v for k, v in state.overrides.items() if k != "brand_name"})
    ids = list(state.candidate_ids)
    if "brand_name" in state.overrides:
        ids = [identifier for identifier in ids if normalize(catalog.by_id[identifier].brand_name) == normalize(state.overrides["brand_name"])]
    matches = [identifier for identifier in ids if passes(catalog.by_id[identifier], effective)]
    conflicts = []
    if not matches:
        # Preserve a matching stated strength before form/package preferences.
        # Every recovery candidate remains unselected until explicit confirmation.
        penalties = {identifier: sum({"strength": 4, "form": 2, "presentation": 1}[f]
                                   for f in mismatches(catalog.by_id[identifier], effective)) for identifier in ids}
        if not penalties:
            return MedicationResult(mention_index=index, mention=mention, status="not_found"), None
        minimum = min(penalties.values())
        matches = [identifier for identifier in ids if penalties[identifier] == minimum]
        conflicts = [f for f in ("strength", "form", "presentation")
                     if any(f in mismatches(catalog.by_id[identifier], effective) for identifier in matches)]
    matches.sort(key=lambda identifier: (-state.scores.get(identifier, 0),
        normalize(catalog.by_id[identifier].brand_name), strength_key(catalog.by_id[identifier].dosage),
        normalize(catalog.by_id[identifier].form), normalize(catalog.by_id[identifier].presentation), identifier))
    next_state = ResolutionState(mention, tuple(matches), state.method, state.scores,
                                 dict(state.overrides), state.name_alias, state.confirm_identity)
    base = dict(mention_index=index, mention=mention, match_method=state.method,
                name_alias=state.name_alias, applied_refinements=state.overrides, conflicting_filters=conflicts)
    if len(matches) == 1 and not state.confirm_identity and not conflicts:
        base["conflicting_filters"] = mismatches(catalog.by_id[matches[0]], mention)
        return MedicationResult(**base, status="resolved", medication=catalog.by_id[matches[0]]), None
    status = "suggestions" if state.confirm_identity else "filters_not_matched" if conflicts else "ambiguous"
    kind = "confirm_name" if state.confirm_identity else "correct_filters" if conflicts else "choose_record"
    selected_field, groups = None, []
    if conflicts:
        selected_field = conflicts[0]
        groups = option_groups(catalog, matches, selected_field)
    elif len(matches) > MAX_RECORD_CHOICES:
        for selected_field in FIELDS:
            groups = option_groups(catalog, matches, selected_field)
            if len(groups) > 1:
                kind = "refine_search"
                break
        else:
            selected_field, groups = None, []
    if offset < 0 or offset >= len(matches):
        raise ValueError("Invalid candidate page")
    preview = matches[offset:offset + MAX_RECORD_CHOICES]
    return MedicationResult(**base, status=status,
        candidates=[catalog.by_id[identifier] for identifier in preview], candidate_count=len(matches),
        candidates_truncated=len(preview) != len(matches), candidate_offset=offset,
        next_candidate_offset=offset + MAX_RECORD_CHOICES if offset + MAX_RECORD_CHOICES < len(matches) else None,
        clarification=MedicationClarification(kind=kind, field=selected_field,
            options=[ClarificationOption(value=value, candidate_count=len(group_ids)) for value, group_ids in groups])), next_state


def resolve_with_state(catalog: MedicationCatalog, mention: MedicationMention, index: int):
    if mention.name is None:
        return MedicationResult(mention_index=index, mention=mention, status="missing_name"), None
    ids, method, scores = identity_candidates(catalog, mention.name)
    if not ids:
        return MedicationResult(mention_index=index, mention=mention, status="not_found"), None
    canonical = lookup_name(mention.name)
    state = ResolutionState(mention, tuple(ids), method, scores,
                            name_alias=canonical if normalize(canonical) != normalize(mention.name) else None,
                            confirm_identity=method in {"partial", "fuzzy"} or alias_requires_confirmation(mention.name))
    return build_resolution(catalog, state, index)


def resolve(catalog: MedicationCatalog, mention: MedicationMention, index: int) -> MedicationResult:
    return resolve_with_state(catalog, mention, index)[0]


def refine_resolution(catalog, state: ResolutionState, current: MedicationResult, field: str, value: str):
    if field == "page":
        if current.next_candidate_offset is None or value != str(current.next_candidate_offset):
            raise ValueError("Choose the offered next candidate page")
        return build_resolution(catalog, state, current.mention_index, offset=current.next_candidate_offset)
    question = current.clarification
    if question is None or question.field != field or value not in {o.value for o in question.options}:
        raise ValueError("Choose a refinement offered for this medication mention")
    groups = {label: ids for label, ids in option_groups(catalog, state.candidate_ids, field)}
    ids = groups.get(value)
    if not ids:
        raise ValueError("Refinement has no permitted candidates")
    next_state = ResolutionState(state.mention, tuple(ids), state.method, state.scores,
                                 {**state.overrides, field: value}, state.name_alias, state.confirm_identity)
    return build_resolution(catalog, next_state, current.mention_index)
