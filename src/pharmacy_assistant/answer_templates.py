"""Compatibility import for :mod:`pharmacy_assistant.core.answer_templates`."""

import sys
from pharmacy_assistant.core import answer_templates as _implementation

sys.modules[__name__] = _implementation
