"""Transport-independent extraction interface consumed by conversation logic."""

from typing import Protocol

from pharmacy_assistant.contracts.nlu_models import InterpretationRequest, InterpretationResponse


class Interpreter(Protocol):
    async def interpret(self, request: InterpretationRequest) -> InterpretationResponse: ...

    async def close(self) -> None: ...
