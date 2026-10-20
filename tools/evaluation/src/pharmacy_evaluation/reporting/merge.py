"""Preserve a first pass and overlay ALL selected rechecks, including failures.

This is a development history, explicitly not a uniform-prompt benchmark.
The later frozen held-out run is the benchmark for the final configuration.
"""

import argparse
import asyncio
from collections import Counter
import json
from pathlib import Path

from pharmacy_evaluation.runners.development import summarize
from pharmacy_evaluation.reporting.io import write_report
from pharmacy_evaluation.datasets.baseline import load_examples, sha256
from pharmacy_language.providers.groq import PROMPT_VERSION
from pharmacy_infrastructure.evidence import resolve_input


async def merge(baseline_path, recheck_path, output):
    if output.exists():
        raise ValueError("Choose a new report path to preserve evidence")
    baseline_path, recheck_path = resolve_input(baseline_path), resolve_input(recheck_path)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    recheck = json.loads(recheck_path.read_text(encoding="utf-8"))
    if any(r["status"] != "complete" or r["split"] != "development" for r in (baseline, recheck)):
        raise ValueError("Both development runs must be complete")
    if any(baseline[k] != recheck[k] for k in ("provider", "model", "output_mode")):
        raise ValueError("Model/provider changes cannot be merged as prompt-only rechecks")
    if any(baseline["sources"][k] != recheck["sources"][k] for k in ("annotations_sha256", "catalogue_sha256", "pharmacy_directory_sha256")):
        raise ValueError("Annotation or data changes cannot be merged")
    for name, digest in baseline["sources"]["backend_sha256"].items():
        if not name.startswith("evaluate_") and name != "baseline_metrics.py" and recheck["sources"]["backend_sha256"][name] != digest:
            raise ValueError("Production backend changes require a new full run")
    originals = {r["id"]: r for r in baseline["predictions"]}
    replacements = {r["id"]: r for r in recheck["predictions"]}
    if len(replacements) != len(recheck["predictions"]) or not replacements.keys() <= originals.keys():
        raise ValueError("Unexpected or duplicate recheck IDs")
    for identifier, row in replacements.items():
        if row["text"] != originals[identifier]["text"]:
            raise ValueError("Recheck text changed")
    baseline["predictions"] = [replacements.get(r["id"], r) for r in baseline["predictions"]]
    baseline["mode"] = "development_history_with_targeted_prompt_rechecks"
    baseline["fingerprint"] = None  # This mixed-history report must never be resumed as a live run.
    baseline["sources"] = recheck["sources"]
    baseline["invocations"] += recheck["invocations"]
    baseline["errors"] += recheck["errors"]
    baseline["current_prompt_version"] = PROMPT_VERSION
    baseline["reviewed_prompt_versions"] = sorted({r["response"]["metadata"]["prompt_version"] for r in baseline["predictions"] if "response" in r})
    baseline["prompt_versions_in_latest_predictions"] = dict(Counter(r["response"]["metadata"]["prompt_version"] for r in baseline["predictions"] if "response" in r))
    baseline["history"] = {"baseline": {"path": str(baseline_path), "sha256": sha256(baseline_path)},
                           "rechecks": {"path": str(recheck_path), "sha256": sha256(recheck_path)},
                           "replaced_job_ids": sorted(replacements), "selection_policy": "All selected rechecks replace prior predictions, regardless of success"}
    baseline["limitations"] += ["Development history combines the original full run with targeted post-fix rechecks across disclosed prompt versions; it is not a single-configuration benchmark.",
                                "Latest-per-case latency/token/schema summaries exclude superseded baseline predictions; reserved attempt counts include both runs. Original complete costs remain in the two source reports."]
    await summarize(baseline, load_examples("development"))
    write_report(output, baseline)
    print(json.dumps({"passed_outcomes": baseline["summary"]["passed_outcomes"], "rechecked_jobs": len(replacements),
                      "prompt_versions": baseline["prompt_versions_in_latest_predictions"]}))
    return baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("rechecks", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(merge(args.baseline, args.rechecks, args.output))


if __name__ == "__main__":
    main()
