"""Compatibility import for :mod:`pharmacy_assistant.core.catalog`."""

import sys
from pharmacy_assistant.core import catalog as _implementation

sys.modules[__name__] = _implementation
