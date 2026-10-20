"""Compatibility import for :mod:`pharmacy_assistant.language.gemini_nlu`."""

import sys
from pharmacy_assistant.language import gemini_nlu as _implementation

sys.modules[__name__] = _implementation
