"""Compatibility import for :mod:`pharmacy_assistant.core.pharmacy_directory`."""

import sys
from pharmacy_assistant.core import pharmacy_directory as _implementation

sys.modules[__name__] = _implementation
