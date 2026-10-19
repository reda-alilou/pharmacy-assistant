"""Development-only baseline. Oracle backend results are separate from live NLU."""

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import statistics

from pharmacy_assistant.baseline_metrics import aggregate_extraction, score_extraction
from pharmacy_assistant.catalog import DATASET, MedicationCatalog
from pharmacy_assistant.chat import ChatService
from pharmacy_assistant.chat_models import ChatRequest, ChatResponse
from pharmacy_assistant.config import ROOT, Settings
from pharmacy_assistant.evaluate_interpretation import run_smoke, write_report
from pharmacy_assistant.evaluation_dataset import DATA_DIRECTORY, EvaluationExample, load_examples, sha256, validate_dataset
from pharmacy_assistant.nlu_models import InferenceError, InterpretationResponse
from pharmacy_assistant.pharmacy_directory import PHARMACIES, PharmacyDirectory


BACKEND_REPORT = ROOT / "reports/development_backend_baseline.json"


class AnnotationInterpreter:
    """Intent/entities supplied by the annotations; never calls a provider."""
    def __init__(self, case: EvaluationExample):
        self.annotations = {turn.text: turn.interpretation for turn in case.context}
        self.annotations[case.text] = case.interpretation

    async def interpret(self, request):
        return InterpretationResponse.model_validate({
            "interpretation": self.annotations[request.text].model_dump(),
            "metadata": {"provider": "gemini", "requested_model": "annotation_oracle", "model": "annotation_oracle",
                         "prompt_version": "not_applicable", "latency_ms": 0, "attempts": 1, "completion_id": None,
                         "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}},
        })

    async def close(self):
        pass


def score_outcome(body: ChatResponse, case: EvaluationExample, catalog: MedicationCatalog) -> dict:
    failures, decisions = [], []
    component = "conversation" if case.kind == "conversation_turn" else "matching"

    def fail(code, area=component):
        failures.append({"component": area, "code": code})

    expected = case.expected
    actual = {result.mention_index: result for result in body.medications}
    for target in expected.medications:
        result = actual.get(target.mention_index)
        passed = False
        if result is not None:
            if target.outcome == "resolved":
                passed = result.status == "resolved" and result.medication is not None and result.medication.source_record_id in target.record_ids
            elif target.outcome == "not_found":
                passed = result.status == "not_found" and result.medication is None
            else:
                candidates = {r.source_record_id for r in result.candidates}
                passed = result.medication is None and result.status in {"ambiguous", "suggestions", "filters_not_matched", "missing_name"}
                passed = passed and set(target.record_ids) <= candidates and result.candidate_count >= target.minimum_candidates
                if target.active_substance:
                    passed = passed and bool(result.candidates) and all(r.active_substance == target.active_substance for r in result.candidates)
                if target.outcome == "confirm_spelling":
                    passed = passed and result.status == "suggestions"
            if result.status == "resolved" and (target.outcome != "resolved" or not passed):
                fail("incorrect_automatic_selection")
        if not passed:
            fail("medication_decision_mismatch")
        decisions.append({"mention_index": target.mention_index, "passed": bool(passed), "expected": target.model_dump(),
                          "observed_status": result.status if result else "no_result"})
    if len(actual) != len(expected.medications):
        fail("unexpected_or_missing_medication_results")
    if expected.require_clarification and body.status != "needs_clarification":
        fail("clarification_not_requested")
    if (expected.medications and all(m.outcome == "resolved" for m in expected.medications)
            and not expected.require_clarification and body.status == "needs_clarification"):
        fail("unexpected_clarification")
    if expected.pharmacy_status is not None:
        if body.pharmacy is None or body.pharmacy.status != expected.pharmacy_status:
            fail("pharmacy_status_mismatch", "pharmacy")
        if expected.pharmacy_ids and (body.pharmacy is None or not set(expected.pharmacy_ids) <= {r.pharmacy_id for r in body.pharmacy.pharmacies}):
            fail("requested_pharmacy_not_returned", "pharmacy")
    if expected.no_medication_facts and (body.medications or body.sources):
        fail("unsupported_request_received_facts", "answer")
    if expected.stock_unknown and any(result.stock_status != "unknown" for result in body.medications):
        fail("stock_claim_not_unknown", "answer")
    if expected.missing_price and (not body.medications or any(r.medication is None or r.medication.ppv_price_mad is not None for r in body.medications)):
        fail("missing_price_not_preserved", "answer")
    if expected.quantity_total_mad is not None:
        text = body.answer.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789."))
        amounts = [float(v.replace(",", ".")) for v in re.findall(r"(\d+(?:[.,]\d{1,2})?)\s*(?:MAD|DH|درهم)", text)]
        if not any(abs(value - expected.quantity_total_mad) < .005 for value in amounts):
            fail("requested_total_missing", "answer" if case.kind == "single_turn" else "conversation")
    for result in body.medications:
        for record in ([result.medication] if result.medication is not None else result.candidates):
            if catalog.get(record.source_record_id) != record:
                fail("record_differs_from_catalogue", "grounding")
    return {"passed": not failures, "failures": failures, "medication_decisions": decisions,
            "broad_candidate_lists": sum(r.candidate_count > 5 for r in body.medications),
            "focused_candidate_lists": sum(r.candidate_count > 5 and r.clarification is not None
                                           and r.clarification.field is not None for r in body.medications)}


async def backend_baseline(output: Path = BACKEND_REPORT, *,
                           catalog_path: Path = DATASET, pharmacy_path: Path = PHARMACIES) -> dict:
    if output.exists():
        raise ValueError("Baseline report exists; choose a new --output path to preserve evidence")
    quality = validate_dataset(catalog_path=catalog_path)
    cases = load_examples("development")
    catalog, directory = MedicationCatalog.from_path(catalog_path), PharmacyDirectory.from_path(pharmacy_path)
    results = []
    for case in cases:
        service = ChatService(catalog, AnnotationInterpreter(case), directory)
        session_id = None
        for turn in case.context:
            context_response = await service.respond(ChatRequest(text=turn.text, session_id=session_id))
            session_id = context_response.session_id
        # Use the public text + opaque session_id contract used by Streamlit.
        # No annotated prior identities are injected into the current extraction.
        body = await service.respond(ChatRequest(text=case.text, session_id=session_id))
        result = {"id": case.id, "group": case.group, "kind": case.kind, "tags": case.tags,
                  **score_outcome(body, case, catalog),
                  "observed": {"status": body.status, "answer": body.answer,
                               "context_inherited_fields": body.context.inherited_fields if body.context else [],
                               "needs_reference": body.context.needs_reference if body.context else False,
                               "order_pricing": body.order_pricing.model_dump(),
                               "medications": [{"mention_index": r.mention_index, "status": r.status,
                                                "record_id": r.medication.source_record_id if r.medication else None,
                                                "candidate_ids": [c.source_record_id for c in r.candidates],
                                                "candidate_count": r.candidate_count,
                                                "pricing": r.pricing.model_dump() if r.pricing else None,
                                                "clarification_field": r.clarification.field if r.clarification else None,
                                                "clarification_kind": r.clarification.kind if r.clarification else None} for r in body.medications],
                               "pharmacy_status": body.pharmacy.status if body.pharmacy else None}}
        results.append(result)
    single = [r for r in results if r["kind"] == "single_turn"]
    conversation = [r for r in results if r["kind"] == "conversation_turn"]
    decisions = [d for row in single for d in row["medication_decisions"]]
    conversation_decisions = [d for row in conversation for d in row["medication_decisions"]]
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "mode": "offline_backend_with_annotated_extraction", "live_provider_requests": 0,
              "is_model_accuracy_measurement": False, "split": "development", "held_out_execution": "not_run",
              "conversation_request_contract": "text + opaque session_id from preceding response",
              "catalogue_sha256": sha256(catalog_path), "pharmacy_directory_sha256": sha256(pharmacy_path),
              "catalogue_path": str(catalog_path), "pharmacy_directory_path": str(pharmacy_path),
              "backend_source_sha256": {name: sha256(ROOT / "src/pharmacy_assistant" / name)
                                        for name in ("chat.py", "chat_models.py", "conversation.py", "pricing.py", "resolution.py", "medication_normalization.py",
                                                     "catalog.py", "pharmacy_directory.py", "pharmacy_normalization.py", "answer_templates.py")},
              "annotations_sha256": sha256(DATA_DIRECTORY / "development.json"), "dataset_validation": quality,
              "summary": {"cases": len(results), "passed_cases": sum(r["passed"] for r in results),
                          "single_turn": {"cases": len(single), "passed_cases": sum(r["passed"] for r in single)},
                          "conversation": {"cases": len(conversation), "passed_cases": sum(r["passed"] for r in conversation)},
                          "conversation_medication_decisions": {"correct": sum(d["passed"] for d in conversation_decisions),
                                                               "total": len(conversation_decisions)},
                          "medication_decisions_with_annotated_extraction": {"correct": sum(d["passed"] for d in decisions),
                                                                          "total": len(decisions)},
                          "failures_by_component": dict(Counter(f["component"] for r in results for f in r["failures"])),
                          "broad_candidate_lists": sum(r["broad_candidate_lists"] for r in results),
                          "focused_candidate_lists": sum(r["focused_candidate_lists"] for r in results)}, "results": results}
    write_report(output, report)
    print(json.dumps(report["summary"]))
    return report


def live_cases():
    # Deliberately no held-out CLI switch in development evaluation.
    return [{"id": c.id, "group": c.group, "text": c.text, "baseline_example": c.model_dump(),
             "scoring_profile": "baseline_v1_slot_alignment_v1"}
            for c in load_examples("development") if c.kind == "single_turn"]


def live_score(response: InterpretationResponse, case: dict) -> dict:
    return score_extraction(response.interpretation, EvaluationExample.model_validate(case["baseline_example"]))


async def live_baseline(settings: Settings, output: Path, *, max_requests=4, resume=False):
    validate_dataset()
    return await run_smoke(settings, output, 0, max_requests=max_requests, resume=resume,
                           cases=live_cases(), score=live_score, summarize_results=aggregate_extraction,
                           fixture_label="baseline_v1/development.json:32_single_turn_examples")


def baseline_summary(backend_path: Path, live_path: Path, output: Path) -> dict:
    """Refresh an evidence summary without any provider calls or held-out execution."""
    backend = json.loads(backend_path.read_text(encoding="utf-8"))
    live = json.loads(live_path.read_text(encoding="utf-8")) if live_path.exists() else None
    by_component = {}
    cases = {c.id: c for c in load_examples("development")}
    for row in backend["results"]:
        for failure in row["failures"]:
            entry = by_component.setdefault(failure["component"], {})
            entry.setdefault(row["id"], {"id": row["id"], "text": cases[row["id"]].text,
                                        "failure_codes": [], "observed": row["observed"]})["failure_codes"].append(failure["code"])
    results = live["results"] if live else []
    latencies = [r["response"]["metadata"]["latency_ms"] for r in results]
    failures = [{"id": r["id"], "intents_correct": r["intents_correct"],
                 "missing_slots": r["missing_entities"], "incorrect_nonnull_slots": r["incorrect_nonnull_entities"]}
                for r in results if not r["intents_correct"] or not r["entities_exact"]]
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "split": "development",
              "held_out_execution": "not_run", "backend_report": str(backend_path),
              "offline_backend": backend["summary"],
              "backend_failures_by_component": {area: list(rows.values()) for area, rows in by_component.items()},
              "backend_failures_are_measured_with_annotated_extraction": True,
              "live_extraction": {"status": live["status"] if live else "not_run", "summary": live["summary"] if live else None,
                                  "remaining_single_turn_cases": 32 - len(results), "prediction_failures": failures,
                                  "latency_ms": {"minimum": min(latencies), "median": statistics.median(latencies),
                                                 "maximum": max(latencies)} if latencies else None,
                                  "attempts_reserved": sum(v["attempts_reserved"] for v in live["invocations"]) if live else 0,
                                  "provider_errors": live["errors"] if live else [],
                                  "raw_schema_validity_rate": None,
                                  "schema_measurement_note": "Adapter jointly validates JSON schema and entity evidence; no separate raw-output schema validity measurement is available."},
              "next_work_in_order": ["Medication alias/form matching and useful options after filter mismatches.",
                                     "Free-text conversational context and corrections.",
                                     "Quantity totals and focused clarification for broad candidate lists."],
              "limits": ["Backend oracle checks are not model accuracy or end-to-end live success measurements.",
                         "Live precision/recall/F1 use only completed cases; unfinished cases remain visible in denominators.",
                         "No held-out inference, backend evaluation or prompt tuning was performed.",
                         "Annotations are assistant-authored and reviewed, without independent human/native-speaker review."]}
    write_report(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description="Development baseline: offline backend or budgeted live extraction; held-out is never executed.")
    parser.add_argument("mode", choices=("offline", "live", "report"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-requests", type=int, default=4)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--catalogue", type=Path, default=DATASET)
    parser.add_argument("--pharmacy-directory", type=Path, default=PHARMACIES)
    args = parser.parse_args()
    try:
        if args.mode == "offline":
            if args.resume:
                parser.error("Offline baseline is deterministic; choose a new output instead of --resume")
            asyncio.run(backend_baseline(args.output or BACKEND_REPORT,
                        catalog_path=args.catalogue, pharmacy_path=args.pharmacy_directory))
        elif args.mode == "live":
            settings = Settings.from_env()
            output = args.output or ROOT / f"reports/development_live_{settings.inference_provider}.json"
            report = asyncio.run(live_baseline(settings, output, max_requests=args.max_requests, resume=args.resume))
            if not report["summary"]["passed"]:
                raise SystemExit(1)
        else:
            settings = Settings.from_env()
            baseline_summary(BACKEND_REPORT, ROOT / f"reports/development_live_{settings.inference_provider}.json",
                             args.output or ROOT / "reports/development_baseline_summary.json")
    except (ValueError, InferenceError) as error:
        parser.exit(2, str(error) + "\n")
    except KeyboardInterrupt:
        parser.exit(130, "Interrupted; saved live cases remain resumable.\n")


if __name__ == "__main__":
    main()
