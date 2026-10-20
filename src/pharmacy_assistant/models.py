"""Compatibility import for :mod:`pharmacy_assistant.core.models`."""

import sys
from pharmacy_assistant.core import models as _implementation

sys.modules[__name__] = _implementation
