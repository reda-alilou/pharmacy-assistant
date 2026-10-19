"""Live Step 3 acceptance checks against an already running local API.

These are development smoke checks, not the held-out Challenge 1 evaluation.
Every invocation sends real requests; saved answers are never substituted.
"""

import argparse
from datetime import datetime, timezone
import time

import requests

from pharmacy_assistant.catalog import ROOT
from pharmacy_assistant.collection_http import write_json


CASES = [
    {"id": "darija-price-stock", "text": "Wach kayn AIRCORT w bch7al?", "kind": "aircort", "intents": ["price", "availability"]},
    {"id": "abip-clarification", "text": "Quel est le prix de ABIP ?", "kind": "abip", "intents": ["price"]},
    {"id": "unknown-medication", "text": "Quel est le prix du médicament XYZZZ999999 ?", "kind": "unknown", "intents": ["price"]},
    {"id": "missing-price", "text": "Quel est le prix de 18F PSMA RIM 250 MBQ / ML, BOITE D'UN FLACON MONODOSE DE 15 ML ?", "kind": "missing", "intents": ["price"]},
    {"id": "arabic-price", "text": "ما ثمن AIRCORT؟", "kind": "aircort", "intents": ["price"]},
    {"id": "arabic-darija-stock", "text": "واش كاين AIRCORT وبشحال؟", "kind": "aircort", "intents": ["price", "availability"]},
    {"id": "mixed-quantity", "text": "Bghit deux boîtes de ABIP 15mg, boîte de 20, شحال الثمن؟", "kind": "mixed", "intents": ["price", "medication_request"]},
    {"id": "rabat-contact", "text": "Donne-moi le téléphone de la Pharmacie Ibn Nafis à Rabat.", "kind": "contact", "intents": ["pharmacy_contact"]},
    {"id": "rabat-duty", "text": "شنو هي صيدليات الحراسة فالرباط الليلة؟", "kind": "duty", "intents": ["pharmacy_on_duty"]},
    {"id": "clinical-boundary", "text": "J'ai mal à la tête, quel médicament dois-je prendre ?", "kind": "unsupported", "intents": ["unsupported"]},
    {"id": "incomplete-price", "text": "Bch7al?", "kind": "incomplete", "intents": ["price"]},
]


def verify(case, body):
    failures = []
    def check(condition, message):
        if not condition:
            failures.append(message)
    interpretation = body["interpretation"]
    check(set(case["intents"]) <= set(interpretation["intents"]), "required intents missing")
    from pharmacy_assistant.nlu_models import Interpretation
    try:
        Interpretation.model_validate(interpretation).validate_evidence(case["text"])
    except ValueError:
        failures.append("entity evidence validation failed")
    results, kind = body["medications"], case["kind"]
    if kind in {"aircort", "mixed", "missing"}:
        expected_id = {"aircort": "771", "mixed": "9079", "missing": "9302"}[kind]
        check(len(results) == 1 and results[0]["status"] == "resolved" and
              results[0]["medication"]["source_record_id"] == expected_id, "wrong medication resolution")
        if kind == "aircort":
            check("83.00 MAD" in body["answer"], "recorded price absent")
        if kind == "mixed":
            check("268.00 MAD" in body["answer"], "presentation price absent")
            check(bool(results and results[0]["mention"]["quantity"]), "quantity missing")
        if kind == "missing":
            check(bool(results and results[0]["medication"] and results[0]["medication"]["ppv_price_mad"] is None), "unknown price not preserved")
            check("MAD" not in body["answer"], "price invented")
    if kind == "abip":
        check(body["status"] == "needs_clarification" and bool(body["continuation_id"]), "no clarification")
        check(len(results) == 1 and {r["source_record_id"] for r in results[0]["candidates"]} == {"9079", "9080"}, "ABIP candidates incorrect")
    if kind == "unknown":
        check(len(results) == 1 and results[0]["status"] == "not_found", "unknown product not preserved")
    if kind in {"contact", "duty"}:
        pharmacy = body["pharmacy"]
        check(pharmacy is not None and pharmacy["status"] == "matches", "Rabat results absent")
        if pharmacy:
            check(pharmacy["duty_status"] == "unverified" and pharmacy["opening_hours_status"] == "unknown", "unverified facts promoted")
            if kind == "contact":
                check(pharmacy["result_count"] == 1 and "0537720657" in body["answer"], "wrong pharmacy contact")
    if kind == "incomplete":
        check(not results and body["status"] == "needs_clarification", "missing identity not clarified")
    if kind == "unsupported":
        check(not results and not body["sources"], "unsupported clinical request produced medication facts")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--interval", type=float, default=30)
    parser.add_argument("--case", action="append", choices=[c["id"] for c in CASES])
    parser.add_argument("--output", type=str, default=str(ROOT / "reports/chat_smoke.json"))
    args = parser.parse_args()
    if not 0 <= args.interval <= 60:
        parser.error("--interval must be between 0 and 60 seconds")
    from pathlib import Path
    output = Path(args.output)
    cases = [case for case in CASES if not args.case or case["id"] in args.case]
    report = {"run_at_utc": datetime.now(timezone.utc).isoformat(), "mode": "live_http",
              "scope": "development_smoke_not_held_out_evaluation", "expected_cases": len(cases), "cases": [], "passed": False}
    write_json(output, report)
    with requests.Session() as session:
        session.trust_env = False  # Local HTTP must bypass unrelated proxy settings.
        for index, case in enumerate(cases):
            if index:
                time.sleep(args.interval)
            started = time.perf_counter()
            entry = {"id": case["id"], "text": case["text"], "failures": []}
            try:
                result = session.post(args.base_url.rstrip("/") + "/chat", json={"text": case["text"]}, timeout=135)
                entry["http_status"] = result.status_code
                entry["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
                entry["response"] = result.json()
                if result.status_code != 200:
                    entry["failures"].append("HTTP request failed")
                else:
                    body = entry["response"]
                    entry["failures"].extend(verify(case, body))
                    # Independently compare every returned fact object with its
                    # canonical record endpoint, including clarification options.
                    for med in body["medications"]:
                        for record in ([med["medication"]] if med["medication"] else med["candidates"]):
                            canonical = session.get(args.base_url.rstrip("/") + "/medications/" + record["source_record_id"], timeout=10)
                            if canonical.status_code != 200 or canonical.json() != record:
                                entry["failures"].append("record differs from canonical endpoint")
                    if case["kind"] == "abip" and body["continuation_id"]:
                        selection = {"continuation_id": body["continuation_id"],
                                     "selections": [{"mention_index": 0, "record_id": "9080"}]}
                        invalid = {**selection, "selections": [{"mention_index": 0, "record_id": "771"}]}
                        rejection = session.post(args.base_url.rstrip("/") + "/chat", json=invalid, timeout=10)
                        followup = session.post(args.base_url.rstrip("/") + "/chat", json=selection, timeout=10)
                        entry["invalid_selection_http_status"] = rejection.status_code
                        entry["followup"] = followup.json()
                        if (rejection.status_code != 422 or followup.status_code != 200 or
                            entry["followup"].get("inference_performed") is not False or
                            "372.00 MAD" not in entry["followup"].get("answer", "")):
                            entry["failures"].append("clarification follow-up failed")
            except (requests.RequestException, ValueError, KeyError) as error:
                entry["failures"].append(f"Check could not complete: {type(error).__name__}")
            entry["passed"] = not entry["failures"]
            report["cases"].append(entry)
            report["passed"] = len(report["cases"]) == len(cases) and all(c["passed"] for c in report["cases"])
            write_json(output, report)
            print(f"{case['id']}: {'PASS' if entry['passed'] else 'FAIL'} ({entry.get('latency_ms', '?')} ms)", flush=True)
    print(f"Saved {len(report['cases'])} live checks; passed={report['passed']}", flush=True)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
