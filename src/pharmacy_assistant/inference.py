"""Provider selection shared by the API and live evaluator."""

from typing import Protocol

from pharmacy_assistant.config import Settings
from pharmacy_assistant.gemini_nlu import GeminiInterpreter
from pharmacy_assistant.nlu import GroqInterpreter
from pharmacy_assistant.nlu_models import InterpretationRequest, InterpretationResponse
from pharmacy_assistant.opencode_nlu import OpenCodeInterpreter
from pharmacy_assistant.quota import AttemptControl


class Interpreter(Protocol):
    async def interpret(self, request: InterpretationRequest) -> InterpretationResponse: ...
    async def close(self) -> None: ...


def create_interpreter(settings: Settings, *, control: AttemptControl | None = None) -> Interpreter:
    control = control if control is not None else AttemptControl.from_settings(settings)
    if settings.inference_provider == "gemini":
        return GeminiInterpreter(settings, control=control)
    if settings.inference_provider == "opencode":
        return OpenCodeInterpreter(settings, control=control)
    return GroqInterpreter(settings, control=control)
