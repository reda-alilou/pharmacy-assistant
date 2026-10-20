"""Versioned internal HTTP contract. No database or provider implementations."""

from typing import Literal
from pydantic import BaseModel, ConfigDict


class LanguageHealth(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["ok"] = "ok"
    service: Literal["language"] = "language"
    contract_version: Literal[1] = 1
    storage_backend: Literal["files", "postgres"]
    interpretation_configured: bool
    interpretation_provider: Literal["groq", "gemini", "opencode"]
    interpretation_model: str


# Only known machine codes cross the boundary. Never forward remote free text.
# Status codes, retry semantics, and French messages are defined locally.
ERRORS = {
    "model_not_configured": (503, False, "Le modèle n'est pas configuré dans le service de langue."),
    "provider_authentication_failed": (503, False, "Le fournisseur a refusé la clé configurée."),
    "provider_permission_denied": (503, False, "Le compte ne peut pas accéder au modèle."),
    "provider_model_unavailable": (503, False, "Le modèle configuré est indisponible."),
    "provider_free_tier_restricted": (503, False, "L'accès direct à cette offre gratuite est refusé."),
    "provider_payment_required": (503, False, "Le fournisseur demande des crédits. Aucun secours payant n'a été appelé."),
    "provider_request_rejected": (503, False, "Le fournisseur a refusé la configuration du modèle."),
    "provider_generation_failed": (502, True, "Le modèle n'a pas produit une extraction valide."),
    "provider_invalid_response": (502, False, "L'extraction du modèle a échoué à la validation."),
    "provider_rate_limited": (429, True, "La limite du fournisseur a été atteinte. Attendez avant de réessayer."),
    "provider_daily_quota_exhausted": (429, False, "Le quota quotidien est épuisé. Attendez sa réinitialisation."),
    "local_rate_limited": (429, True, "Les demandes sont espacées pour préserver le quota."),
    "quota_state_unavailable": (503, False, "Le suivi du quota est indisponible. Les appels au modèle sont bloqués."),
    "provider_timeout": (504, True, "Le fournisseur a dépassé le délai autorisé. La demande a pu être comptabilisée."),
    "provider_unreachable": (503, True, "Le fournisseur du modèle est inaccessible."),
    "provider_unavailable": (503, True, "Le fournisseur du modèle est temporairement indisponible."),
    "provider_refused": (422, False, "Le modèle a refusé cette demande. Reformulez votre question."),
    "language_unavailable": (503, True, "Le service de langue est inaccessible. Réessayez manuellement ; la demande a pu être comptabilisée."),
    "language_timeout": (504, True, "Le service de langue a dépassé le délai autorisé. La demande a pu être comptabilisée ; vérifiez avant de réessayer."),
    "language_invalid_response": (502, False, "La réponse du service de langue est invalide. Aucune réponse factuelle n'a été générée."),
}
