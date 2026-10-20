"""Provider selection shared by the API and live evaluator."""

from pharmacy_assistant.config import Settings
from pharmacy_assistant.language.gemini_nlu import GeminiInterpreter
from pharmacy_assistant.language.nlu import GroqInterpreter
from pharmacy_assistant.contracts.interpreter import Interpreter
from pharmacy_assistant.language.opencode_nlu import OpenCodeInterpreter
from pharmacy_assistant.language.quota import AttemptControl


def create_interpreter(settings: Settings, *, control: AttemptControl | None = None) -> Interpreter:
    control = control if control is not None else AttemptControl.from_settings(settings)
    if settings.inference_provider == "gemini":
        return GeminiInterpreter(settings, control=control)
    if settings.inference_provider == "opencode":
        return OpenCodeInterpreter(settings, control=control)
    return GroqInterpreter(settings, control=control)
