"""Compatibility import for :mod:`pharmacy_assistant.core.chat_models`."""

import sys
from pharmacy_assistant.core import chat_models as _implementation

sys.modules[__name__] = _implementation
