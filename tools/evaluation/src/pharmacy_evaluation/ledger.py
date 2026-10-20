"""Live evaluation uses the language-owned PostgreSQL attempt ledger."""
from pharmacy_language.quota.control import AttemptControl


def create_control(settings, **kwargs):
    return AttemptControl.from_settings(settings, **kwargs)
