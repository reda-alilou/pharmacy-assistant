"""Budgeted live development evaluation, including real conversation replay.

Saved predictions are evaluation evidence only, never a fallback in the demo.
There is deliberately no held-out option in this development command.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import time
from types import SimpleNamespace
import uuid

from pharmacy_assistant.baseline_metrics import aggregate_extraction, score_extraction
from pharmacy_assistant.catalog import DATASET, MedicationCatalog
from pharmacy_assistant.chat import ChatService
from pharmacy_assistant.chat_models import ChatRequest
from pharmacy_assistant.config import ROOT, Settings
from pharmacy_assistant.evaluate_baseline import score_outcome
from pharmacy_assistant.evaluate_interpretation import write_report
from pharmacy_assistant.evaluation_dataset import DATA_DIRECTORY, GROUPS, EvaluationExample, load_examples, sha256
from pharmacy_assistant.evaluation_state import fingerprint, report_lock
from pharmacy_assistant.inference import create_interpreter
from pharmacy_assistant.nlu_models import InferenceError, Interpretation, InterpretationRequest, InterpretationResponse
from pharmacy_assistant.pharmacy_directory import PHARMACIES, PharmacyDirectory
from pharmacy_assistant.quota import AttemptControl


VERSION = 1
BACKEND_FILES = ("chat.py", "chat_models.py", "conversation.py", "pricing.py", "resolution.py",
                 "medication_normalization.py", "catalog.py", "pharmacy_directory.py",
                 "pharmacy_normalization.py", "answer_templates.py", "baseline_metrics.py",
                 "evaluate_baseline.py", "evaluate_development.py", "paths.py", "database.py", "config.py", "api.py") + tuple(
    path.relative_to(ROOT / "src/pharmacy_assistant").as_posix()
    for package in ("core", "language", "contracts", "transport")
    for path in sorted((ROOT / "src/pharmacy_assistant" / package).rglob("*.py"))
)


def provenance(split="development"):
    return {"annotations_sha256": sha256(DATA_DIRECTORY / f"{split}.json"),
            "catalogue_sha256": sha256(DATASET), "pharmacy_directory_sha256": sha256(PHARMACIES),
            "backend_sha256": {name: sha256(ROOT / "src/pharmacy_assistant" / name) for name in BACKEND_FILES}}


def development_jobs(cases):
    # Do not merge identical text across cases: each dialogue gets independent inference.
    jobs = []
    for case in cases:
        for index, turn in enumerate(case.context):
            jobs.append({"id": f"{case.id}:context:{index}", "case_id": case.id,
                         "group": case.group, "role": "context", "text": turn.text})
        jobs.append({"id": case.id, "case_id": case.id, "group": case.group,
                     "role": "current", "text": case.text})
    return jobs


class AuditedGroqClient:
    """Observe actual SDK completions without changing production decoding/retries."""
    def __init__(self, client, audit):
        self.client, self.audit, self.text = client, audit, ""
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **options):
        started = time.monotonic()
        row = {"schema_valid": None, "evidence_valid": None}
        self.audit.append(row)
        try:
            completion = await self.client.chat.completions.create(**options)
            choice = completion.choices[0]
            row["finish_reason"] = choice.finish_reason
            row["model"] = completion.model
            row["usage"] = {key: getattr(completion.usage, key, None)
                            for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
            try:
                parsed = Interpretation.model_validate_json(choice.message.content)
            except (ValueError, TypeError):
                row["schema_valid"] = False
            else:
                row["schema_valid"] = True
                try:
                    parsed.validate_evidence(self.text)
                    row["evidence_valid"] = True
                except ValueError:
                    row["evidence_valid"] = False
            return completion
        except BaseException:
            row["transport_failed"] = True
            raise
        finally:
            row["latency_ms"] = round((time.monotonic() - started) * 1000, 2)

    async def close(self):
        await self.client.close()


class RecordedInterpreter:
    """Replay this case's captured live outputs through the unchanged chat service."""
    def __init__(self, rows):
        self.rows = iter(rows)

    async def interpret(self, request):
        row = next(self.rows)
        if row["text"] != request.text or "response" not in row:
            raise ValueError("Missing or mismatched captured live prediction")
        return InterpretationResponse.model_validate(row["response"])


async def summarize(report, cases):
    predictions = {r["id"]: r for r in report["predictions"]}
    catalog, directory = MedicationCatalog.from_path(), PharmacyDirectory.from_path()
    raw_scores, effective_scores, outcomes = [], [], []
    for case in cases:
        row = predictions.get(case.id)
        if row and "response" in row:
            parsed = InterpretationResponse.model_validate(row["response"]).interpretation
            raw = {"id": case.id, "group": case.group, **score_extraction(parsed, case)}
            # Contextual gold intent refers to the dialogue, while the model sees
            # only the current text. Score these intents after context merging.
            if case.kind == "single_turn":
                raw_scores.append(raw)
        ids = [f"{case.id}:context:{i}" for i in range(len(case.context))] + [case.id]
        rows = [predictions.get(identifier) for identifier in ids]
        if any(r is None for r in rows):
            continue
        if any("response" not in r for r in rows):
            outcomes.append({"id": case.id, "group": case.group, "kind": case.kind,
                             "passed": False, "failure": "inference_rejected"})
            continue
        service = ChatService(catalog, RecordedInterpreter(rows), directory)
        token = None
        for saved in rows:
            body = await service.respond(ChatRequest(text=saved["text"], session_id=token))
            token = body.session_id
        effective = body.context.effective_interpretation if body.context else body.interpretation
        effective_scores.append({"id": case.id, "group": case.group, **score_extraction(effective, case)})
        outcomes.append({"id": case.id, "group": case.group, "kind": case.kind,
                         **score_outcome(body, case, catalog), "response": body.model_dump(mode="json")})
    audits = [a for r in report["predictions"] for a in r.get("attempt_audit", [])]
    # Pending HTTP failures are not predictions, but still count as attempts.
    audits += [a for e in report["errors"] if not e.get("saved_as_prediction") for a in e.get("attempt_audit", [])]
    returned = [a for a in audits if a["schema_valid"] is not None]
    latencies = [r["response"]["metadata"]["latency_ms"] for r in report["predictions"] if "response" in r]
    report["raw_single_turn_scores"] = raw_scores
    report["effective_scores"] = effective_scores
    report["outcomes"] = outcomes
    report["summary"] = {
        "cases": len(cases), "inference_jobs": len(development_jobs(cases)),
        "completed_inference_jobs": len(predictions),
        "accepted_inference_jobs": sum("response" in r for r in predictions.values()),
        "raw_single_turn_extraction": aggregate_extraction(raw_scores, sum(c.kind == "single_turn" for c in cases)),
        "effective_dialogue_extraction": aggregate_extraction(effective_scores, len(cases)),
        "completed_outcomes": len(outcomes), "passed_outcomes": sum(r["passed"] for r in outcomes),
        "outcomes_by_group": {g: {"completed": sum(r["group"] == g for r in outcomes),
                                     "passed": sum(r["group"] == g and r["passed"] for r in outcomes)} for g in GROUPS},
        "medication_resolution": {"correct": sum(d["passed"] for r in outcomes for d in r.get("medication_decisions", [])),
                                  "scored": sum(len(r.get("medication_decisions", [])) for r in outcomes),
                                  "expected": sum(len(c.expected.medications) for c in cases)},
        "schema": {"returned_completions": len(returned),
                   "valid_completions": sum(a["schema_valid"] for a in returned),
                   "validity_rate": sum(a["schema_valid"] for a in returned) / len(returned) if returned else None,
                   "evidence_rejections": sum(a.get("evidence_valid") is False for a in returned),
                   "transport_failures": sum(a.get("transport_failed", False) for a in audits)},
        "latency_ms": {"min": min(latencies), "median": statistics.median(latencies),
                       "p95": sorted(latencies)[max(0, math.ceil(.95 * len(latencies)) - 1)],
                       "max": max(latencies)} if latencies else None,
        "tokens_returned_completions": {key: sum((a.get("usage", {}).get(key) or 0) for a in returned)
                                       for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
    }


async def run(settings, output, *, max_requests=4, resume=False, interval=0, factory=create_interpreter,
              case_ids=None, split="development", freeze=None, examples_path=None):
    if max_requests < 0 or not 0 <= interval <= 60:
        raise ValueError("Use a nonnegative attempt budget and interval between zero and 60 seconds")
    if split not in {"development", "held_out"}:
        raise ValueError("Unknown split")
    if split == "held_out":
        if freeze is None or case_ids or examples_path:
            raise ValueError("Held-out execution requires a freeze and the complete split")
        from pharmacy_assistant.evaluation_freeze import verify_freeze
        verify_freeze(settings, freeze)  # Before loading held-out examples or making any request.
    if examples_path:
        cases = [EvaluationExample.model_validate(row) for row in json.loads(Path(examples_path).read_text(encoding="utf-8"))]
        if not cases or len({c.id for c in cases}) != len(cases) or any(c.split != "development" for c in cases):
            raise ValueError("Custom regression examples require unique development IDs")
    else:
        cases = load_examples(split)
    if case_ids:
        if not set(case_ids) <= {c.id for c in cases}:
            raise ValueError("Unknown development case ID")
        cases = [c for c in cases if c.id in case_ids]
    jobs = development_jobs(cases)
    signature, sources = fingerprint(settings, jobs), provenance(split)
    if examples_path:
        sources.update(annotations_sha256=sha256(Path(examples_path)), annotations_path=str(examples_path))
    with report_lock(output):
        if resume:
            report = json.loads(output.read_text(encoding="utf-8"))
            if report.get("version") != VERSION or report["fingerprint"] != signature or report["sources"] != sources:
                raise ValueError("Evaluation configuration, code, data or prompt changed; choose a new report")
            by_id, seen = {j["id"]: j for j in jobs}, set()
            for row in report["predictions"]:
                if row["id"] in seen or row["id"] not in by_id or row["text"] != by_id[row["id"]]["text"]:
                    raise ValueError("Duplicate or mismatched saved prediction")
                seen.add(row["id"])
                if "response" in row:
                    response = InterpretationResponse.model_validate(row["response"])
                    response.interpretation.validate_evidence(row["text"])
                    if response.metadata.provider != settings.inference_provider or response.metadata.requested_model != settings.inference_model:
                        raise ValueError("Saved prediction provider/model mismatch")
        else:
            if output.exists():
                raise ValueError("Preserve previous evidence: choose a new report or use --resume")
            report = {"version": VERSION, "evaluation_id": uuid.uuid4().hex, "fingerprint": signature,
                      "generated_at_utc": datetime.now(timezone.utc).isoformat(), "sources": sources,
                      "mode": "live_predictions_with_backend_replay", "split": split,
                      "held_out_execution": "executed_after_implementation_freeze" if split == "held_out" else "not_run",
                      "freeze": {"path": str(freeze), "sha256": sha256(Path(freeze))} if freeze else None,
                      "selected_case_ids": [c.id for c in cases], "provider": settings.inference_provider,
                      "model": settings.inference_model, "output_mode": settings.inference_output_mode,
                      "predictions": [], "errors": [], "invocations": [],
                      "limitations": ["Synthetic assistant-authored/reviewed annotations; no independent speaker review.",
                                      f"{sum(c.kind == 'single_turn' for c in cases)} standalone extractions scored raw; all {len(cases)} cases scored after real context merging.",
                                      f"{sum(len(c.context) for c in cases)} context setup calls are additional to the {len(cases)} scored current messages.",
                                      "Invalid outputs remain failed cases; transport/quota failures remain visibly pending.",
                                      "Schema rate uses SDK-returned completions; HTTP failures are a separate denominator.",
                                      "Token usage excludes transport failures that returned no usage.",
                                      "Saved model outputs replayed only for evaluation; the demo has no saved-answer fallback."]}
        await summarize(report, cases)
        done = {r["id"] for r in report["predictions"]}
        pending = [j for j in jobs if j["id"] not in done]
        if not pending:
            write_report(output, report)
            return report
        control = AttemptControl.from_settings(settings, budget_id=uuid.uuid4().hex, wait=True)
        for previous in report["invocations"]:
            counts = control.store.budget_counts(previous["id"], report["evaluation_id"])
            if counts["max_requests"] != previous["max_requests"] or counts["attempts_reserved"] < previous["attempts_reserved"]:
                raise ValueError("Saved report and durable request ledger disagree")
            previous.update(counts)
        control.store.new_budget(control.budget_id, report["evaluation_id"], max_requests)
        invocation = {"id": control.budget_id, "started_at_utc": datetime.now(timezone.utc).isoformat()}
        report["invocations"].append(invocation)
        report["status"] = "running"
        interpreter, audit_client = None, None

        def save():
            invocation.update(control.store.budget_counts(control.budget_id, report["evaluation_id"]))
            write_report(output, report)

        save()
        try:
            interpreter = factory(settings, control=control)
            if settings.inference_provider == "groq" and getattr(interpreter, "client", None) is not None:
                audit_client = AuditedGroqClient(interpreter.client, [])
                interpreter.client = audit_client
            for index, job in enumerate(pending):
                if index and interval:
                    await asyncio.sleep(interval)
                row = dict(job)
                if audit_client:
                    audit_client.audit, audit_client.text = [], job["text"]
                try:
                    response = await interpreter.interpret(InterpretationRequest(text=job["text"]))
                    row["response"] = response.model_dump(mode="json")
                except InferenceError as error:
                    safe_error = error.detail.model_dump(mode="json")
                    row["error"] = safe_error
                    row["attempt_audit"] = audit_client.audit if audit_client else []
                    rejected = error.detail.code in {"provider_invalid_response", "provider_refused", "provider_generation_failed"}
                    report["errors"].append({"id": job["id"], "at_utc": datetime.now(timezone.utc).isoformat(),
                                             "error": safe_error, "attempt_audit": row["attempt_audit"],
                                             "saved_as_prediction": rejected})
                    if not rejected:
                        report["status"] = "paused_budget" if error.detail.code == "evaluation_budget_exhausted" else "paused_provider"
                        print(f"{job['id']}: {error.detail.code}; progress saved", flush=True)
                        break
                row["attempt_audit"] = audit_client.audit if audit_client else []
                report["predictions"].append(row)
                save()
                print(f"{len(report['predictions'])}/{len(jobs)} {job['id']}: "
                      f"{'accepted' if 'response' in row else row['error']['code']}", flush=True)
            else:
                report["status"] = "complete"
        except BaseException:
            report["status"] = "interrupted"
            raise
        finally:
            invocation["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
            try:
                save()
                await summarize(report, cases)
                save()
            finally:
                if interpreter:
                    await interpreter.close()
        summary = report["summary"]
        print(json.dumps({"status": report["status"], "completed_jobs": summary["completed_inference_jobs"],
                          "passed_outcomes": summary["passed_outcomes"], "attempts": invocation["attempts_reserved"]}), flush=True)
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, default=4)
    parser.add_argument("--interval", type=float, default=0, help="Evaluation-only pacing; does not change demo configuration")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--case-ids", nargs="+", help="Development-only targeted rechecks; original reports remain separate")
    parser.add_argument("--examples", type=Path, help="Explicit development-regression fixture; never a new held-out benchmark")
    args = parser.parse_args()
    asyncio.run(run(Settings.from_env(), args.output, max_requests=args.max_requests,
                    resume=args.resume, interval=args.interval, case_ids=args.case_ids, examples_path=args.examples))


if __name__ == "__main__":
    main()
