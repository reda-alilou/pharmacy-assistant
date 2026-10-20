"""Compatibility import for :mod:`pharmacy_assistant.contracts.nlu_models`."""

import sys
from pharmacy_assistant.contracts import nlu_models as _implementation

sys.modules[__name__] = _implementation
