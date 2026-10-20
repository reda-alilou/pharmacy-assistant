"""PostgreSQL orchestration around the existing deterministic conversation engine."""

import asyncio

from pydantic import ValidationError

from pharmacy_contracts.errors import StorageUnavailable
from pharmacy_core.conversation.service import ChatService
from pharmacy_core.conversation.models import ChatResponse
from pharmacy_core.conversation.errors import ChatError
from pharmacy_core.storage.postgres.state_codec import encode_state, decode_state, encode_choice, decode_choice


class PersistentChatService:
    def __init__(self, catalog, interpreter, directory, store):
        self.catalog, self.interpreter, self.directory, self.store = catalog, interpreter, directory, store

    async def respond(self, request):
        turn = await asyncio.to_thread(self.store.begin, request)
        if "replay" in turn:
            return ChatResponse.model_validate(turn["replay"]["response"])
        service = ChatService(self.catalog, self.interpreter, self.directory, ttl_seconds=1800)
        effective_request = request
        try:
            if turn["state"]:
                if turn["state"].get("version") != 1:
                    raise StorageUnavailable()
                if turn["continuation"]:
                    service.pending[request.continuation_id] = decode_choice(turn["state"])
                elif turn["state"]["state"] is not None:
                    service.sessions[request.session_id] = decode_state(turn["state"]["state"])
                else:
                    if request.reference_index is not None:
                        raise ChatError("invalid_reference", "Aucun choix de contexte n'a été proposé.")
                    effective_request = request.model_copy(update={"session_id": None})
            response = await service.respond(effective_request)
            state = encode_state(service.sessions[response.session_id])
            choice = encode_choice(service.pending[response.continuation_id]) if response.continuation_id else None
            return await asyncio.to_thread(self.store.complete, turn, response, state, choice)
        except Exception as error:
            code = getattr(error, "code", None) or getattr(getattr(error, "detail", None), "code", "request_failed")
            try:
                await asyncio.to_thread(self.store.fail, turn, code)
            except StorageUnavailable:
                pass  # Original failure is more useful; the pending row cannot advance context.
            if isinstance(error, (KeyError, ValidationError)):
                raise StorageUnavailable() from None
            raise
