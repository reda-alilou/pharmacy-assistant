"""Compatibility import for :mod:`pharmacy_assistant.language.quota`."""

import sys
from pharmacy_assistant.language import quota as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
