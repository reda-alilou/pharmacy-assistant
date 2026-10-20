"""Record and enforce the implementation/configuration used for held-out testing."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from pharmacy_assistant.config import ROOT, Settings
from pharmacy_assistant.evaluate_interpretation import write_report
from pharmacy_assistant.evaluation_dataset import sha256
from pharmacy_assistant.nlu import PROMPT_VERSION


def public_configuration(settings):
    provider = settings.inference_provider
    return {"provider": provider, "model": settings.inference_model,
            "output_mode": settings.inference_output_mode, "prompt_version": PROMPT_VERSION,
            "timeout_seconds": getattr(settings, f"{provider}_timeout_seconds"),
            "max_output_tokens": getattr(settings, f"{provider}_max_" + ("output_tokens" if provider == "gemini" else "completion_tokens"))}


def snapshot():
    paths = sorted((ROOT / "src/pharmacy_assistant").rglob("*.py"))
    paths += [ROOT / p for p in (
        "pyproject.toml", "uv.lock", "data/evaluation/baseline_v1/manifest.json",
        "data/evaluation/baseline_v1/development.json", "data/evaluation/baseline_v1/held_out.json",
        "data/processed/ammps_medications_enriched.jsonl", "data/processed/pharmacies_rabat.jsonl",
        "data/processed/medicament_medications.jsonl", "data/processed/saydalia_medications.jsonl",
        "data/processed/pharmacy_duty_observations.jsonl")]
    return {p.relative_to(ROOT).as_posix(): sha256(p) for p in paths}


def create_freeze(settings, development_report: Path, output: Path):
    if output.exists():
        raise ValueError("Freeze exists; preserve it and choose a new filename")
    report = json.loads(development_report.read_text(encoding="utf-8"))
    metrics = report["dialogue_intents_and_current_slots"]
    if (report["split"] != "development" or report["status"] != "complete" or not metrics["passed"]
            or not report["raw_standalone"]["passed"] or report["backend"]["passed"] != 40):
        raise ValueError("Complete passing development evaluation is required before freezing")
    if any(report[key] != public_configuration(settings)[key] for key in ("provider", "model", "output_mode")):
        raise ValueError("Current inference configuration differs from evaluated configuration")
    files = snapshot()
    for name, expected in report["sources"]["backend_sha256"].items():
        # Evaluation-only extensions may change after a development run; every
        # production backend file must still be exactly the evaluated version.
        if name.startswith("evaluate_") or name == "baseline_metrics.py":
            continue
        if files[f"src/pharmacy_assistant/{name}"] != expected:
            raise ValueError("Production backend changed since development evaluation")
    source = json.loads(Path(report["source_report"]).read_text(encoding="utf-8"))
    if sha256(Path(report["source_report"])) != report["source_report_sha256"]:
        raise ValueError("Development evidence changed after scoring")
    permitted_versions = source.get("reviewed_prompt_versions", [PROMPT_VERSION])
    if PROMPT_VERSION not in permitted_versions or source.get("current_prompt_version", PROMPT_VERSION) != PROMPT_VERSION:
        raise ValueError("Current prompt has no reviewed development evidence")
    if source.get("history"):
        for origin in (source["history"]["baseline"], source["history"]["rechecks"]):
            if sha256(Path(origin["path"])) != origin["sha256"]:
                raise ValueError("Development history source changed")
    for row in source["predictions"]:
        if "response" in row and row["response"]["metadata"]["prompt_version"] not in permitted_versions:
            raise ValueError("Unreviewed prompt version in development predictions")
    freeze = {"version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "development_report": str(development_report), "development_report_sha256": sha256(development_report),
              "configuration": public_configuration(settings), "files": files,
              "development_evidence_mode": report.get("evidence_mode", "live_predictions"),
              "development_prompt_versions": permitted_versions,
              "held_out_status_at_freeze": "not_run", "secrets_included": False}
    write_report(output, freeze)
    return freeze


def verify_freeze(settings, path):
    freeze = json.loads(Path(path).read_text(encoding="utf-8"))
    if freeze["configuration"] != public_configuration(settings) or freeze["files"] != snapshot():
        raise ValueError("Frozen code, data or model settings changed; held-out execution refused")
    if sha256(Path(freeze["development_report"])) != freeze["development_report_sha256"]:
        raise ValueError("Frozen development report changed")
    return freeze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    freeze = create_freeze(Settings.from_env(), args.development_report, args.output)
    print(json.dumps({"frozen_files": len(freeze["files"]), "configuration": freeze["configuration"]}))


if __name__ == "__main__":
    main()
