"""Offline scoring of captured predictions; never sends inference requests."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics

from pharmacy_evaluation.scoring.extraction import aggregate_extraction, f1_counts, score_extraction
from pharmacy_evaluation.reporting.io import write_report
from pharmacy_evaluation.datasets.baseline import DATA_DIRECTORY, GROUPS, EvaluationExample, load_examples, sha256
from pharmacy_contracts.interpretation import Interpretation, InterpretationResponse
from pharmacy_infrastructure.evidence import resolve_input


def latency(values):
    if not values:
        return None
    ordered = sorted(values)
    return {"count": len(values), "minimum": min(values), "median": statistics.median(values),
            "p95_nearest_rank": ordered[math.ceil(.95 * len(values)) - 1], "maximum": max(values)}


def analyze(source: Path, output: Path, *, split="development"):
    if output.exists():
        raise ValueError("Choose a new report path to preserve evidence")
    source = resolve_input(source)
    saved = json.loads(source.read_text(encoding="utf-8"))
    annotation_path = resolve_input(saved["sources"].get("annotations_path", DATA_DIRECTORY / f"{split}.json"))
    if saved["split"] != split or saved["sources"]["annotations_sha256"] != sha256(annotation_path):
        raise ValueError("Prediction report does not match frozen annotations")
    cases = ([EvaluationExample.model_validate(row) for row in json.loads(annotation_path.read_text(encoding="utf-8"))]
             if "annotations_path" in saved["sources"] else load_examples(split))
    if saved.get("selected_case_ids"):
        cases = [c for c in cases if c.id in saved["selected_case_ids"]]
    rows = {r["id"]: r for r in saved["predictions"]}
    outcomes = {r["id"]: r for r in saved["outcomes"]}
    raw_scores, dialogue_scores, failures = [], [], []
    for case in cases:
        row = rows.get(case.id)
        if row is None:
            continue
        if "response" not in row:
            blank = case.interpretation.model_copy(deep=True)
            blank.entities.medications = []
            for key in ("pharmacy", "city", "area", "date", "time", "symptom"):
                setattr(blank.entities, key, None)
            scored = score_extraction(blank, case)
            scored.update(intents_correct=False, intent_counts=f1_counts(0, 0, len(case.interpretation.intents)),
                          entities_exact=False, language_correct=False, reply_language_correct=False, reply_script_correct=False)
            failures.append({"id": case.id, "reason": "inference_rejected", "error": row["error"]})
        else:
            parsed = InterpretationResponse.model_validate(row["response"]).interpretation
            parsed.validate_evidence(case.text)
            scored = score_extraction(parsed, case)
        scored = {"id": case.id, "group": case.group, **scored}
        if case.kind == "single_turn":
            raw_scores.append(scored)
        # Gold slots describe exact spans of THIS message, not inherited data.
        # Use raw slots for entity scoring and effective dialogue intents for
        # intent scoring. Do not penalize correct inheritance as hallucination.
        outcome = outcomes.get(case.id)
        if outcome and "response" in outcome:
            body = outcome["response"]
            effective = Interpretation.model_validate(body["context"]["effective_interpretation"] if body.get("context") else body["interpretation"])
            intent_score = score_extraction(effective, case)
            dialogue = {**scored, "intents_correct": intent_score["intents_correct"],
                        "intent_counts": intent_score["intent_counts"]}
        elif outcome:
            dialogue = {**scored, "intents_correct": False,
                        "intent_counts": f1_counts(0, 0, len(case.interpretation.intents))}
        else:
            continue
        dialogue_scores.append(dialogue)
        if not dialogue["intents_correct"] or not dialogue["entities_exact"] or not outcome["passed"]:
            failures.append({"id": case.id, "text": case.text, "raw_slot_score": scored,
                             "dialogue_intents_correct": dialogue["intents_correct"],
                             "backend_passed": outcome["passed"], "backend_failures": outcome.get("failures", [])})
    accepted = [r for r in saved["predictions"] if "response" in r]
    current = [r for r in accepted if r["role"] == "current"]
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "split": split,
        "source_report": str(source), "source_report_sha256": sha256(source), "sources": saved["sources"],
        "provider": saved["provider"], "model": saved["model"], "output_mode": saved["output_mode"],
        "evidence_mode": saved["mode"], "history": saved.get("history"),
        "prompt_versions": saved.get("prompt_versions_in_latest_predictions") or dict(Counter(
            r["response"]["metadata"]["prompt_version"] for r in saved["predictions"] if "response" in r)),
        "status": saved["status"], "held_out_execution": saved["held_out_execution"],
        "scoring_contract": "Raw current-message slots, effective dialogue intents; raw standalone metrics also shown separately.",
        "annotation_contract_note": "Follow-up annotations contain contextual intents but only current-message entity spans. Inherited medicine identities are assessed by backend resolution, not current-message slot F1.",
        "raw_standalone": aggregate_extraction(raw_scores, sum(c.kind == "single_turn" for c in cases)),
        "dialogue_intents_and_current_slots": aggregate_extraction(dialogue_scores, len(cases)),
        "backend": {"total": len(cases), "completed": len(outcomes), "passed": sum(r["passed"] for r in outcomes.values()),
                    "by_group": saved["summary"]["outcomes_by_group"],
                    "medication_resolution": saved["summary"]["medication_resolution"]},
        "schema": saved["summary"]["schema"],
        "latency_ms_all_calls": latency([r["response"]["metadata"]["latency_ms"] for r in accepted]),
        "latency_ms_current_messages_by_group": {g: latency([r["response"]["metadata"]["latency_ms"] for r in current if r["group"] == g]) for g in GROUPS},
        "language_diagnostics": {g: {"scored": sum(r["group"] == g for r in dialogue_scores),
                                     **{field: sum(r["group"] == g and r[field] for r in dialogue_scores)
                                        for field in ("language_correct", "reply_language_correct", "reply_script_correct")}}
                                 for g in GROUPS},
        "medication_resolution_by_group": {g: {"correct": sum(d["passed"] for r in outcomes.values() if r["group"] == g for d in r.get("medication_decisions", [])),
                                              "scored": sum(len(r.get("medication_decisions", [])) for r in outcomes.values() if r["group"] == g),
                                              "expected": sum(len(c.expected.medications) for c in cases if c.group == g)} for g in GROUPS},
        "usage_returned_completions": saved["summary"]["tokens_returned_completions"],
        "attempts_reserved": sum(i["attempts_reserved"] for i in saved["invocations"]),
        "provider_errors": [e for e in saved["errors"] if e["error"]["code"] != "evaluation_budget_exhausted"],
        "budget_checkpoints": sum(e["error"]["code"] == "evaluation_budget_exhausted" for e in saved["errors"]),
        "failures": failures,
        "limits": saved["limitations"] + ["This report supersedes the captured run's preliminary effective entity scores, which compared inherited entities against current-message-only annotations.",
                                          "Latency is the production interpretation adapter duration, including any retry; it is not browser round-trip latency.",
                                          "F1 measures extraction labels; backend outcome checks measure structured behavior, not independent review of every generated sentence."]}
    write_report(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "held_out"), default="development")
    args = parser.parse_args()
    report = analyze(args.source, args.output, split=args.split)
    print(json.dumps({"status": report["status"], "backend": report["backend"]}, indent=2))


if __name__ == "__main__":
    main()
