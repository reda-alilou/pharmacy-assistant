"""Sent to an isolated test core through stdin; never included in runtime images.

Seeds a synthetic clarification with a local fixture, not a model call or runtime
fallback. The existing production conversation engine and database store are used.
"""

import asyncio
import json
import sys

from pharmacy_assistant.config import CoreSettings
from pharmacy_assistant.contracts.nlu_models import InterpretationResponse
from pharmacy_assistant.core.chat_models import ChatRequest
from pharmacy_assistant.core.storage.catalogue import load_catalogue
from pharmacy_assistant.core.storage.chat import PersistentChatService
from pharmacy_assistant.core.storage.conversations import ConversationStore
from pharmacy_assistant.database import create_database_engine


class FixtureInterpreter:
    async def interpret(self, request):
        assert request.text == "Quel est le prix de ABIP 15mg ?"
        return InterpretationResponse.model_validate({
            "interpretation": {
                "language": "fr", "reply_language": "fr", "reply_script": "latin", "intents": ["price"],
                "entities": {"medications": [{"name": "ABIP", "strength": "15mg", "quantity": None,
                    "form": None, "presentation": None}], "pharmacy": None, "city": None,
                    "area": None, "date": None, "time": None, "symptom": None}},
            "metadata": {"provider": "groq", "output_mode": "json_object", "requested_model": "deployment-fixture",
                "model": "deployment-fixture", "prompt_version": "deployment-fixture", "latency_ms": 0.0,
                "attempts": 1, "completion_id": None,
                "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}}})


async def main():
    payload = json.load(sys.stdin)
    engine = create_database_engine(CoreSettings.from_env().core_database_url.get_secret_value())
    try:
        catalogue, directory = load_catalogue(engine)
        service = PersistentChatService(catalogue, FixtureInterpreter(), directory, ConversationStore(engine))
        result = await service.respond(ChatRequest(text="Quel est le prix de ABIP 15mg ?",
            session_id=payload["session_id"], request_id=payload["request_id"]))
        assert result.status == "needs_clarification"
        print(json.dumps({"session_id": result.session_id, "continuation_id": result.continuation_id}))
    finally:
        engine.dispose()


asyncio.run(main())
