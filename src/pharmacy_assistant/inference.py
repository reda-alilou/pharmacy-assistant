"""Compatibility import for :mod:`pharmacy_assistant.language.inference`."""

import sys
from pharmacy_assistant.language import inference as _implementation

sys.modules[__name__] = _implementation
