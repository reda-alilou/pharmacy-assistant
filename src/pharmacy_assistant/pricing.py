"""Compatibility import for :mod:`pharmacy_assistant.core.pricing`."""

import sys
from pharmacy_assistant.core import pricing as _implementation

sys.modules[__name__] = _implementation
