"""Compatibility import for :mod:`pharmacy_assistant.language.opencode_nlu`."""

import sys
from pharmacy_assistant.language import opencode_nlu as _implementation

sys.modules[__name__] = _implementation
