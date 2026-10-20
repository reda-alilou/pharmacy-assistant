"""Compatibility import for :mod:`pharmacy_assistant.core.conversation`."""

import sys
from pharmacy_assistant.core import conversation as _implementation

sys.modules[__name__] = _implementation
