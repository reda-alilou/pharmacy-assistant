"""Real API/provider checks driven through Streamlit AppTest, not a browser.

No inference is mocked. This verifies rendered Streamlit elements and widget
actions; screenshots and responsive browser layout still require browser QA.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import time

from streamlit.testing.v1 import AppTest

from pharmacy_assistant.collection_http import write_json
from pharmacy_assistant.demo import EXAMPLES


ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=30)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/streamlit_live_smoke.json")
    args = parser.parse_args()
    if not 0 <= args.interval <= 60:
        parser.error("--interval must be between 0 and 60 seconds")
    report = {"run_at_utc": datetime.now(timezone.utc).isoformat(), "mode": "live_api_via_streamlit_apptest",
              "mocked_inference": False, "browser_visual_qa": "not_run_no_connected_browser",
              "expected_cases": len(EXAMPLES), "cases": [], "passed": False}
    write_json(args.output, report)
    app = AppTest.from_file(str(ROOT / "src/pharmacy_assistant/demo.py"), default_timeout=150).run()
    for index, (label, text) in enumerate(EXAMPLES):
        if index:
            time.sleep(args.interval)
        entry = {"label": label, "text": text, "failures": [], "attempts": []}
        try:
            next(button for button in app.button if button.label == label).click().run()
            for attempt in range(2):
                if len(app.exception):
                    entry["failures"].append("Streamlit script exception")
                    break
                turn = app.session_state["turns"][-1]
                entry["attempts"].append({"response": turn["response"], "error": turn["error"]})
                if turn["response"] or attempt == 1:
                    break
                error = turn["error"] or {}
                if not error.get("retryable"):
                    break
                delay = error.get("retry_after_seconds") or 0
                if delay > 60:
                    break
                time.sleep(max(1, delay))
                # Explicitly exercise the visible manual retry button once.
                next(button for button in app.button if button.label == "Réessayer").click().run()
            turn = app.session_state["turns"][-1]
            body = turn["response"]
            if not body:
                entry["failures"].append("Provider/API request did not succeed")
            else:
                meds = body["medications"]
                if label == "Choix ABIP":
                    if not meds or {r["source_record_id"] for r in meds[0]["candidates"]} != {"9079", "9080"}:
                        entry["failures"].append("Wrong clarification candidates")
                    else:
                        next(button for button in app.button if not button.disabled and "BOITE DE 30" in button.label).click().run()
                        selected = app.session_state["turns"][-1]["response"]
                        entry["selection_response"] = selected
                        if (not selected or selected["inference_performed"] or
                            selected["medications"][0]["medication"]["source_record_id"] != "9080" or
                            "372.00 MAD" not in selected["answer"]):
                            entry["failures"].append("Clarification selection failed")
                else:
                    expected_id = "9079" if label == "Mixte" else "771"
                    if (len(meds) != 1 or not meds[0]["medication"] or
                        meds[0]["medication"]["source_record_id"] != expected_id):
                        entry["failures"].append("Wrong medication resolution")
                    if label == "Mixte" and (not meds or not meds[0]["mention"]["quantity"]):
                        entry["failures"].append("Quantity not extracted")
                    if label == "العربية" and body["interpretation"]["reply_script"] != "arabic":
                        entry["failures"].append("Arabic reply direction missing")
                    if label == "Darija" and body["interpretation"]["reply_language"] != "darija":
                        entry["failures"].append("Darija reply language incorrect")
                    if not any(body["answer"] in item.value for item in app.markdown):
                        entry["failures"].append("Answer not rendered")
                if len(app.json) == 0 or not any(expander.label == "Extraction JSON" for expander in app.expander):
                    entry["failures"].append("Extracted JSON missing")
                if not body["sources"]:
                    entry["failures"].append("Source details missing")
        except (StopIteration, KeyError, IndexError, RuntimeError) as error:
            entry["failures"].append(type(error).__name__)
        entry["passed"] = not entry["failures"]
        report["cases"].append(entry)
        report["passed"] = len(report["cases"]) == len(EXAMPLES) and all(c["passed"] for c in report["cases"])
        write_json(args.output, report)
        print(f"Example {index + 1}/{len(EXAMPLES)}: passed={entry['passed']} attempts={len(entry['attempts'])}", flush=True)
    print(f"Live Streamlit AppTest checks passed={report['passed']}; browser visual QA not run", flush=True)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
