"""Compatibility import for :mod:`pharmacy_assistant.core.pharmacy_normalization`."""

import sys
from pharmacy_assistant.core import pharmacy_normalization as _implementation

sys.modules[__name__] = _implementation
