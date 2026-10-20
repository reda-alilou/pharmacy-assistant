"""Provider selection shared by the API and live evaluator."""

from pharmacy_language.config import LanguageSettings as Settings
from pharmacy_language.providers.gemini import GeminiInterpreter
from pharmacy_language.providers.groq import GroqInterpreter
from pharmacy_contracts.interpreter import Interpreter
from pharmacy_language.providers.opencode import OpenCodeInterpreter
from pharmacy_language.quota.control import AttemptControl


def create_interpreter(settings: Settings, *, control: AttemptControl | None = None) -> Interpreter:
    control = control if control is not None else AttemptControl.from_settings(settings)
    try:
        if settings.inference_provider == "gemini":
            return GeminiInterpreter(settings, control=control)
        if settings.inference_provider == "opencode":
            return OpenCodeInterpreter(settings, control=control)
        return GroqInterpreter(settings, control=control)
    except BaseException:
        control.close()
        raise
