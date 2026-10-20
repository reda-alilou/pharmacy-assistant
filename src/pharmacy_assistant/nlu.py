"""Compatibility import for :mod:`pharmacy_assistant.language.nlu`."""

import sys
from pharmacy_assistant.language import nlu as _implementation

sys.modules[__name__] = _implementation
