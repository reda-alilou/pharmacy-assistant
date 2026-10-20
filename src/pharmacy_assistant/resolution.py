"""Compatibility import for :mod:`pharmacy_assistant.core.resolution`."""

import sys
from pharmacy_assistant.core import resolution as _implementation

sys.modules[__name__] = _implementation
