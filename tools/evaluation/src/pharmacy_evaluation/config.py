"""Evaluation owns provider configuration and access to its PostgreSQL ledger."""
from pharmacy_language.config import LanguageSettings


class EvaluationSettings(LanguageSettings):
    """Explicit live tools share language quotas, never core credentials."""
