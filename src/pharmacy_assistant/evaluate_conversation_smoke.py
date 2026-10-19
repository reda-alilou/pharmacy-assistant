"""Small explicit live conversation check, sharing the normal quota gate."""

import argparse
from datetime import datetime, timezone
import asyncio
import json
from pathlib import Path
import uuid

from pharmacy_assistant.catalog import MedicationCatalog
from pharmacy_assistant.chat import ChatService
from pharmacy_assistant.chat_models import ChatRequest
from pharmacy_assistant.config import ROOT, Settings
from pharmacy_assistant.evaluation_state import report_lock
from pharmacy_assistant.inference import create_interpreter
from pharmacy_assistant.nlu import PROMPT_VERSION
from pharmacy_assistant.nlu_models import InferenceError
from pharmacy_assistant.pharmacy_directory import PharmacyDirectory
from pharmacy_assistant.quota import AttemptControl


async def run_smoke(settings: Settings, output: Path, *, max_requests=2, quantity_check=False):
    if not 0 <= max_requests <= 4:
        raise ValueError("Use a budget between zero and four provider attempts")
    with report_lock(output):
        if output.exists():
            raise ValueError("Choose a new output filename to preserve existing evidence")
        control = AttemptControl.from_settings(settings, wait=True)
        evaluation_id, budget_id = f"conversation-smoke:{uuid.uuid4().hex}", uuid.uuid4().hex
        control.store.new_budget(budget_id, evaluation_id, max_requests)
        control.budget_id = budget_id
        interpreter = create_interpreter(settings, control=control)
        report = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(), "mode": "live_conversation_smoke",
            "provider": settings.inference_provider, "requested_model": settings.inference_model,
            "prompt_version": PROMPT_VERSION, "is_general_accuracy_measurement": False,
            "scenario": "presentation_and_quantity" if quantity_check else "presentation_followup",
            "held_out_execution": "not_run", "status": "incomplete", "turns": [],
            "error": None, "evaluation_id": evaluation_id, "budget_id": budget_id,
        }

        def save():
            report["budget"] = control.store.budget_counts(budget_id, evaluation_id)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        save()
        try:
            service = ChatService(MedicationCatalog.from_path(), interpreter, PharmacyDirectory.from_path())
            token = None
            texts = ["Quel est le prix de ABIP ?", "Lboita dyal 30 3afak."]
            if quantity_check:
                texts.append("Et pour deux boîtes ?")
            for index, text in enumerate(texts):
                body = await service.respond(ChatRequest(text=text, session_id=token))
                token = body.session_id
                result = body.medications[0] if len(body.medications) == 1 else None
                if index == 0:
                    passed = bool(result and result.status == "ambiguous" and
                                  {r.source_record_id for r in result.candidates} == {"9079", "9080"})
                else:
                    passed = bool(result and result.medication is not None and result.medication.source_record_id == "9080" and
                                  body.context is not None and "medications.0.name" in body.context.inherited_fields)
                    if index == 2:
                        passed = bool(passed and result.pricing and result.pricing.presentation_count == 2 and
                            result.pricing.unit_price_mad == "372.00" and result.pricing.total_price_mad == "744.00" and
                            body.order_pricing.total_price_mad == "744.00" and "744.00 MAD" in body.answer)
                report["turns"].append({"text": text, "passed": passed, "response": body.model_dump(mode="json")})
                save()
                if not passed:
                    report["status"] = "failed_behavior"
                    break
            else:
                report["status"] = "passed"
        except InferenceError as error:
            report["status"] = "stopped_provider_error"
            report["error"] = {"code": error.detail.code, "status_code": error.status_code,
                               "retry_after_seconds": error.detail.retry_after_seconds}
        finally:
            await interpreter.close()
            save()
        print(json.dumps({"status": report["status"], "completed_turns": len(report["turns"]),
                          "error": report["error"], "budget": report["budget"]}))
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-requests", type=int)
    parser.add_argument("--quantity-check", action="store_true", help="Add a third turn checking two packages at the stored price")
    args = parser.parse_args()
    maximum = args.max_requests if args.max_requests is not None else 3 if args.quantity_check else 2
    output = args.output or ROOT / ("reports/quantity_live_smoke.json" if args.quantity_check else "reports/conversation_live_smoke.json")
    report = asyncio.run(run_smoke(Settings.from_env(), output, max_requests=maximum, quantity_check=args.quantity_check))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
