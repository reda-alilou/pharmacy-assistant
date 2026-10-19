"""Explicit live Step 2 check, separate from offline tests and Step 5 evaluation."""

import argparse
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pharmacy_assistant.config import ROOT, Settings
from pharmacy_assistant.nlu import InferenceError, PROMPT_VERSION
from pharmacy_assistant.inference import create_interpreter
from pharmacy_assistant.nlu_models import Interpretation, InterpretationRequest, InterpretationResponse, normalize_span
from pharmacy_assistant.evaluation_state import fingerprint, report_lock
from pharmacy_assistant.quota import AttemptControl


CASES = ROOT / "data/evaluation/interpretation_smoke.json"


def compare_entities(actual: Interpretation, case: dict) -> dict:
    """Report missing fields separately from incorrect non-null critical values."""
    missing, incorrect = [], []
    remaining = list(actual.entities.medications)

    def compare(field, value, allowed):
        acceptable = [normalize_span(item) if item is not None else None for item in allowed]
        observed = normalize_span(value) if value is not None else None
        if observed not in acceptable:
            (missing if value is None else incorrect).append(field)

    for index, expected in enumerate(case["expected_medications"]):
        allowed_names = [normalize_span(n) if n is not None else None for n in expected["name"]]
        match = next((m for m in remaining if (
            normalize_span(m.name) if m.name is not None else None
        ) in allowed_names), None)
        if match is None:
            missing.append(f"medications[{index}]")
            continue
        remaining.remove(match)
        for field, allowed in expected.items():
            compare(f"medications[{index}].{field}", getattr(match, field), allowed)
    if remaining:
        incorrect.append("unexpected_medication_mentions")
    for field, allowed in case["expected_context"].items():
        compare(field, getattr(actual.entities, field), allowed)
    return {"missing_entities": missing, "incorrect_nonnull_entities": incorrect,
            "entities_exact": not missing and not incorrect}


def summarize(results: list[dict], total_cases: int) -> dict:
    completed = [r for r in results if "response" in r]
    correct = sum(r.get("intents_correct", False) for r in results)
    entity_exact = sum(r.get("entities_exact", False) for r in results)
    incorrect = sum(len(r.get("incorrect_nonnull_entities", [])) for r in results)
    return {
        "total_cases": total_cases,
        "completed_cases": len(completed),
        "intents_correct": correct,
        "entities_exact_cases": entity_exact,
        "incorrect_nonnull_entities": incorrect,
        "passed": (len(completed) == total_cases == 12 and correct >= 10
                   and entity_exact >= 10 and incorrect == 0),
    }


def write_report(path: Path, report: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def default_score(response: InterpretationResponse, case: dict) -> dict:
    return {"intents_correct": set(response.interpretation.intents) == set(case["expected_intents"]),
            **compare_entities(response.interpretation, case)}


async def run_smoke(settings: Settings, output: Path, interval: float, *,
                    max_requests: int = 4, resume: bool = False, cases: list[dict] | None = None,
                    score=None, summarize_results=None, fixture_label: str | None = None) -> dict:
    """Budget counts outbound attempts, including retries, with durable reservations."""
    if max_requests < 0 or not 0 <= interval <= 60:
        raise ValueError("Budget must be non-negative and interval between 0 and 60")
    with report_lock(output):
        return await _run_smoke(settings, output, interval, max_requests=max_requests, resume=resume,
                                cases=cases, score=score, summarize_results=summarize_results, fixture_label=fixture_label)


async def _run_smoke(settings: Settings, output: Path, interval: float, *,
                     max_requests: int, resume: bool, cases=None, score=None, summarize_results=None, fixture_label=None) -> dict:
    cases = cases if cases is not None else json.loads(CASES.read_text(encoding="utf-8"))
    summary_fn = summarize_results or summarize
    score = score or default_score
    signature = fingerprint(settings, cases)
    if resume:
        if not output.exists():
            raise ValueError("There is no report to resume. Start without --resume first.")
        report = json.loads(output.read_text(encoding="utf-8"))
        if report.get("report_version") != 2 or report.get("fingerprint") != signature:
            raise ValueError("Cannot resume: model, prompt, schema, settings or examples changed. Use a new output path.")
        by_id = {c["id"]: c for c in cases}
        seen = set()
        for result in report["results"]:
            if result["id"] in seen or result["id"] not in by_id:
                raise ValueError("Invalid or duplicate saved case")
            seen.add(result["id"])
            response = InterpretationResponse.model_validate(result["response"])
            case = by_id[result["id"]]
            response.interpretation.validate_evidence(case["text"])
            if (result["text"] != case["text"] or response.metadata.provider != settings.inference_provider
                    or response.metadata.requested_model != settings.inference_model):
                raise ValueError("Saved response does not match this evaluation")
            result.update(score(response, case))
    else:
        if output.exists():
            raise ValueError("Report already exists. Use --resume or choose a new --output path.")
        report = {
            "report_version": 2, "evaluation_id": uuid.uuid4().hex, "fingerprint": signature,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "mode": "live", "provider": settings.inference_provider, "model": settings.inference_model,
            "output_mode": settings.inference_output_mode, "prompt_version": PROMPT_VERSION,
            "fixture": fixture_label or str(CASES.relative_to(ROOT)), "results": [], "errors": [], "invocations": [],
            "acceptance": "See the dataset scoring profile" if summarize_results else "12 completed cases, at least 10 correct intent sets and 10 exact entity cases, no incorrect non-null entities",
        }
    report["summary"] = summary_fn(report["results"], len(cases))
    completed_ids = {r["id"] for r in report["results"]}
    pending = [case for case in cases if case["id"] not in completed_ids]
    if not pending:
        report["status"] = "passed" if report["summary"]["passed"] else "failed"
        write_report(output, report)
        print("All cases already completed; no provider requests sent.", flush=True)
        return report
    if not settings.interpretation_configured:
        report["status"] = "not_run_missing_key"
        write_report(output, report)
        print(f"Live checks NOT RUN: configure {settings.inference_key_name} locally.", flush=True)
        return report

    control = AttemptControl.from_settings(settings, budget_id=uuid.uuid4().hex, wait=True)
    # Never reset counters silently if the ledger was removed or an older report
    # was copied without it. A reservation committed before a crash may exceed
    # the last saved report count; recover that conservative count from SQLite.
    for previous in report["invocations"]:
        counts = control.store.budget_counts(previous["id"], report["evaluation_id"])
        if (counts["max_requests"] != previous["max_requests"]
                or counts["attempts_reserved"] < previous["attempts_reserved"]):
            raise ValueError("The report and request ledger disagree. No provider request was sent.")
        previous.update(counts)
    control.store.new_budget(control.budget_id, report["evaluation_id"], max_requests)
    invocation = {"id": control.budget_id, "started_at_utc": datetime.now(timezone.utc).isoformat()}
    report["invocations"].append(invocation)
    report["status"] = "running"
    interpreter = None

    def checkpoint():
        invocation.update(control.store.budget_counts(control.budget_id, report["evaluation_id"]))
        report["summary"] = summary_fn(report["results"], len(cases))
        write_report(output, report)

    checkpoint()
    try:
        # Missing/corrupt quota state fails closed before any HTTP call.
        interpreter = create_interpreter(settings, control=control)
        for index, case in enumerate(pending):
            if index and interval:
                await asyncio.sleep(interval)
            try:
                response = await interpreter.interpret(InterpretationRequest(text=case["text"]))
            except InferenceError as error:
                report["errors"].append({"id": case["id"], "at_utc": datetime.now(timezone.utc).isoformat(),
                                         "error": error.detail.model_dump(mode="json")})
                report["status"] = {
                    "evaluation_budget_exhausted": "paused_budget",
                    "local_rate_limited": "paused_spacing",
                    "provider_rate_limited": "paused_quota",
                    "provider_daily_quota_exhausted": "paused_daily_quota",
                }.get(error.detail.code, "stopped_provider_error")
                print(f"{case['id']}: {error.detail.code}; saved progress, case remains pending.", flush=True)
                break
            result = {"id": case["id"], "group": case["group"], "text": case["text"],
                      "response": response.model_dump(mode="json"),
                      **score(response, case)}
            report["results"].append(result)
            checkpoint()
            print(f"{len(report['results'])}/{len(cases)} {case['id']}: intents={result['intents_correct']} "
                  f"entities={result['entities_exact']} latency={response.metadata.latency_ms}ms", flush=True)
        else:
            report["summary"] = summary_fn(report["results"], len(cases))
            report["status"] = "passed" if report["summary"]["passed"] else "failed"
    except asyncio.CancelledError:
        report["status"] = "interrupted"
        raise
    except BaseException:
        report["status"] = "interrupted"
        raise
    finally:
        invocation["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        try:
            checkpoint()
        finally:
            if interpreter is not None:
                await interpreter.close()
    print(json.dumps({"status": report["status"], **report["summary"]}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description="Run the 12 live multilingual Step 2 checks.")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-requests", type=int, default=4, help="Maximum outbound attempts this invocation, including retries (default: 4).")
    parser.add_argument("--resume", action="store_true", help="Continue this report, skipping completed cases.")
    parser.add_argument("--interval", type=float, default=0, help="Extra delay between cases; shared request spacing still applies (default: 0).")
    args = parser.parse_args()
    if args.max_requests < 0:
        parser.error("--max-requests must be non-negative")
    if not 0 <= args.interval <= 60:
        parser.error("--interval must be between 0 and 60 seconds")
    settings = Settings.from_env()
    output = args.output or ROOT / f"reports/interpretation_budgeted_{settings.inference_provider}.json"
    try:
        report = asyncio.run(run_smoke(settings, output, args.interval, max_requests=args.max_requests, resume=args.resume))
    except (ValueError, InferenceError) as error:
        parser.exit(2, str(error) + "\n")
    except KeyboardInterrupt:
        parser.exit(130, "Interrupted; saved cases remain resumable.\n")
    if not report["summary"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
