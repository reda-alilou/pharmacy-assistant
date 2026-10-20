"""Transport-independent extraction interface consumed by conversation logic."""

from typing import Protocol

from pharmacy_contracts.interpretation import InterpretationRequest, InterpretationResponse


class Interpreter(Protocol):
    async def interpret(self, request: InterpretationRequest) -> InterpretationResponse: ...

    async def close(self) -> None: ...
