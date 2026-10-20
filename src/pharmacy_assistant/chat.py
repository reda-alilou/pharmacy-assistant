"""Compatibility import for :mod:`pharmacy_assistant.core.chat`."""

import sys
from pharmacy_assistant.core import chat as _implementation

sys.modules[__name__] = _implementation
