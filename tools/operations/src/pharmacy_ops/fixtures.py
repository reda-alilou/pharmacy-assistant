"""Generate browser-test fixtures from the real engine/catalogue, with no hosted calls."""

import asyncio
import json
from pathlib import Path

class FixtureInterpreter:
    def __init__(self): self.result = None; self.calls = 0
    async def interpret(self, request): self.calls += 1; return self.result
    async def close(self): pass

from pharmacy_contracts.interpretation import InterpretationResponse
from pharmacy_core.medications.catalog import MedicationCatalog
from pharmacy_core.conversation.service import ChatService
from pharmacy_core.conversation.models import ChatRequest
from pharmacy_core.conversation.models import MedicationResult, SourceInfo
from pharmacy_core.medications.pricing import apply_pricing
from pharmacy_core.pharmacies.directory import PharmacyDirectory
from pharmacy_infrastructure.paths import ROOT


def extraction(*, quantity=None, pharmacy=False):
    return InterpretationResponse.model_validate({"interpretation": {
        "language": "fr", "reply_language": "fr", "reply_script": "latin", "intents": ["pharmacy_search" if pharmacy else "price"],
        "entities": {"medications": [] if pharmacy else [{"name": None if quantity else "ABIP", "strength": None if quantity else "15mg",
            "quantity": quantity, "form": None, "presentation": None}], "city": "Rabat" if pharmacy else None,
            "area": "Agdal" if pharmacy else None, "pharmacy": None, "date": None, "time": None, "symptom": None}},
        "metadata": {"provider": "groq", "output_mode": "json_object", "requested_model": "browser-test-fixture",
            "model": "browser-test-fixture", "prompt_version": "browser-test-fixture", "latency_ms": 0.0,
            "attempts": 1, "completion_id": None, "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}}})


async def generate(target: Path):
    catalogue = MedicationCatalog.from_path()
    fake = FixtureInterpreter()
    fake.result = extraction()
    service = ChatService(catalogue, fake, PharmacyDirectory.from_path())
    initial = await service.respond(ChatRequest(text="Quel est le prix de ABIP 15mg ?"))
    selected = await service.respond(ChatRequest(continuation_id=initial.continuation_id,
        selections=[{"mention_index": 0, "record_id": "9080"}]))
    fake.result = extraction(quantity="deux boîtes")
    two = await service.respond(ChatRequest(text="Et pour deux boîtes ?", session_id=selected.session_id))
    fake.result = extraction(pharmacy=True)
    pharmacy = await service.respond(ChatRequest(text="Une pharmacie à Agdal, Rabat"))
    missing = selected.model_dump(mode="json")
    empty_price = next(record for record in catalogue.records if record.ppv_price_mad is None)
    missing["medications"][0].update(medication=empty_price.model_dump(mode="json"), pricing=None)
    missing["answer"] = "Le prix public de cette présentation n’est pas renseigné dans le catalogue."
    missing["sources"] = [{"source": empty_price.source, "url": empty_price.source_url,
        "fetched_at_utc": empty_price.source_fetched_at_utc, "record_ids": [empty_price.source_record_id]}]
    first_line = selected.medications[0].model_copy(deep=True)
    first_line.mention.quantity = "deux boîtes"
    second_record = next(record for record in catalogue.records if record.brand_name == "AIRCORT" and record.ppv_price_mad is not None)
    second_line = MedicationResult(mention_index=1, mention={"name": "AIRCORT", "strength": None, "quantity": "une boîte", "form": None, "presentation": None},
        status="resolved", medication=second_record)
    multi = selected.model_copy(deep=True)
    multi.medications = [first_line, second_line]
    multi.order_pricing = apply_pricing(multi.medications)
    multi.sources = [SourceInfo(source=record.source, url=record.source_url,
        fetched_at_utc=record.source_fetched_at_utc, record_ids=[record.source_record_id])
        for record in (first_line.medication, second_record)]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"initial": initial.model_dump(mode="json"), "selected": selected.model_dump(mode="json"),
        "two": two.model_dump(mode="json"), "pharmacy": pharmacy.model_dump(mode="json"), "missing": missing,
        "multi": multi.model_dump(mode="json")}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert fake.calls == 3
    print("Exported browser fixtures from local facts and mock interpretation; zero hosted requests.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'apps/web/tests/fixtures/responses.json')
    args = parser.parse_args()
    asyncio.run(generate(args.output))


if __name__ == '__main__':
    main()
