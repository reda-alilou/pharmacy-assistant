"""Micro metrics with one-to-one mention alignment and explicit denominators."""

from functools import lru_cache

from pharmacy_assistant.evaluation_dataset import EvaluationExample, GROUPS
from pharmacy_assistant.nlu_models import Interpretation, normalize_span


MEDICATION_FIELDS = ("name", "strength", "quantity", "form", "presentation")
CONTEXT_FIELDS = ("pharmacy", "city", "area", "date", "time", "symptom")


def f1_counts(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def score_extraction(actual: Interpretation, case: EvaluationExample) -> dict:
    gold = case.interpretation
    correct = set(actual.intents) & set(gold.intents)
    intents = f1_counts(len(correct), len(set(actual.intents) - set(gold.intents)), len(set(gold.intents) - set(actual.intents)))
    expected, predicted = gold.entities.medications, actual.entities.medications

    def allowed(index, field):
        value = getattr(expected[index], field)
        return [normalize_span(v) for v in ([value] if value is not None else [])
                + case.alternatives.get(f"medications.{index}.{field}", [])]

    @lru_cache(None)
    def alignment(index, used):
        if index == len(expected):
            return 0, ()
        score, pairs = alignment(index + 1, used)
        best = score, ((index, None),) + pairs
        for j, mention in enumerate(predicted):
            if used & (1 << j):
                continue
            weight = sum(getattr(mention, field) is not None and normalize_span(getattr(mention, field)) in allowed(index, field)
                         for field in MEDICATION_FIELDS)
            tail_score, tail_pairs = alignment(index + 1, used | (1 << j))
            candidate = (weight + tail_score, ((index, j),) + tail_pairs)
            if candidate[0] > best[0]:
                best = candidate
        return best

    tp = fp = fn = 0
    missing, incorrect = [], []
    field_counts = {field: {"tp": 0, "fp": 0, "fn": 0} for field in MEDICATION_FIELDS + CONTEXT_FIELDS}

    def compare(path, expected_value, actual_value, alternatives=()):
        nonlocal tp, fp, fn
        accepted = {normalize_span(v) for v in ([expected_value] if expected_value is not None else []) + list(alternatives)}
        counts = field_counts[path.rsplit(".", 1)[-1]]
        if actual_value is not None:
            if normalize_span(actual_value) in accepted:
                tp += 1
                counts["tp"] += 1
            else:
                fp += 1
                counts["fp"] += 1
                incorrect.append(path)
        if expected_value is not None and (actual_value is None or normalize_span(actual_value) not in accepted):
            fn += 1
            counts["fn"] += 1
            missing.append(path)

    pairs = alignment(0, 0)[1]
    used_predictions = set()
    for i, j in pairs:
        if j is not None:
            used_predictions.add(j)
        for field in MEDICATION_FIELDS:
            compare(f"medications.{i}.{field}", getattr(expected[i], field),
                    getattr(predicted[j], field) if j is not None else None,
                    case.alternatives.get(f"medications.{i}.{field}", []))
    for j, mention in enumerate(predicted):
        if j not in used_predictions:
            for field in MEDICATION_FIELDS:
                compare(f"unexpected_medication.{j}.{field}", None, getattr(mention, field))
    for field in CONTEXT_FIELDS:
        compare(field, getattr(gold.entities, field), getattr(actual.entities, field), case.alternatives.get(field, []))
    return {"intents_correct": set(actual.intents) == set(gold.intents),
            "entities_exact": fp == 0 and fn == 0, "intent_counts": intents,
            "slot_counts": f1_counts(tp, fp, fn), "missing_entities": missing,
            "slot_by_field": {field: f1_counts(**counts) for field, counts in field_counts.items()},
            "incorrect_nonnull_entities": incorrect,
            "language_correct": actual.language == case.group,
            "reply_language_correct": actual.reply_language == gold.reply_language,
            "reply_script_correct": actual.reply_script == gold.reply_script}


def aggregate_extraction(results: list[dict], total_cases: int) -> dict:
    def aggregate(rows):
        data = {"completed_cases": len(rows)}
        for source, target in (("intent_counts", "intent_micro"), ("slot_counts", "entity_slot_micro")):
            data[target] = f1_counts(*(sum(r[source][field] for r in rows) for field in ("tp", "fp", "fn")))
        data["entity_slots_by_field"] = {slot: f1_counts(*(sum(r["slot_by_field"][slot][key] for r in rows)
                                                      for key in ("tp", "fp", "fn")))
                                         for slot in MEDICATION_FIELDS + CONTEXT_FIELDS}
        return data
    overall = aggregate(results)
    by_group = {g: aggregate([r for r in results if r["group"] == g]) for g in GROUPS}
    return {"total_cases": total_cases, **overall,
            "intents_correct": sum(r["intents_correct"] for r in results),
            "entities_exact_cases": sum(r["entities_exact"] for r in results),
            "incorrect_nonnull_entities": sum(len(r["incorrect_nonnull_entities"]) for r in results),
            "by_group": by_group,
            "passed": len(results) == total_cases and total_cases > 0
            and (overall["intent_micro"]["f1"] or 0) >= .90
            and (overall["entity_slot_micro"]["f1"] or 0) >= .85
            and all((v["intent_micro"]["f1"] or 0) >= .80 for v in by_group.values())}
