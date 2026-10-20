"""Compatibility import for :mod:`pharmacy_assistant.core.medication_normalization`."""

import sys
from pharmacy_assistant.core import medication_normalization as _implementation

sys.modules[__name__] = _implementation
