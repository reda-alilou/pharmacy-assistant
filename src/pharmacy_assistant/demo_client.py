"""Streamlit's HTTP boundary. No provider keys, inference, or saved replies."""

from dataclasses import dataclass
import math
import os
from urllib.parse import urlsplit

import requests
from pydantic import ValidationError

from pharmacy_assistant.chat_models import ChatRequest, ChatResponse
from pharmacy_assistant.models import HealthResponse


ERROR_MESSAGES = {
    "language_unavailable": "Le service de langue est inaccessible. Vérifiez son démarrage puis réessayez manuellement.",
    "language_timeout": "Le service de langue n'a pas répondu à temps. La demande a pu être comptabilisée ; évitez les renvois répétés.",
    "language_invalid_response": "La réponse du service de langue est invalide. Aucune réponse factuelle n'a été générée.",
    "storage_unavailable": "La base de données est indisponible. Votre demande n'a pas pu être terminée.",
    "model_not_configured": "La clé du modèle doit être configurée sur le serveur FastAPI.",
    "provider_authentication_failed": "Le fournisseur a refusé la clé configurée sur le serveur.",
    "provider_permission_denied": "Le compte ne peut pas accéder au modèle configuré.",
    "provider_model_unavailable": "Le modèle configuré n'est pas disponible pour ce projet ou cette API.",
    "provider_free_tier_restricted": "OpenCode réserve cette offre gratuite à son propre outil. L'accès direct depuis cette application est refusé.",
    "provider_payment_required": "Le fournisseur demande une facturation ou des crédits. Aucun modèle payant de secours n'a été appelé.",
    "provider_request_rejected": "Le fournisseur a refusé la configuration du modèle.",
    "provider_generation_failed": "Le modèle n'a pas produit une extraction JSON valide. Aucune réponse factuelle n'a été générée.",
    "provider_invalid_response": "L'extraction du modèle a échoué à la validation. Aucune réponse factuelle n'a été générée.",
    "provider_rate_limited": "La limite du fournisseur a été atteinte. Attendez avant de réessayer.",
    "provider_daily_quota_exhausted": "Le quota quotidien de Gemini est épuisé. Réessayez après sa réinitialisation.",
    "local_rate_limited": "Les demandes sont espacées pour préserver le quota. Attendez le délai indiqué.",
    "quota_state_unavailable": "Le suivi local du quota est indisponible. Les nouvelles demandes au modèle sont bloquées.",
    "provider_timeout": "Le fournisseur du modèle a dépassé le délai autorisé.",
    "provider_unreachable": "Le serveur ne parvient pas à joindre le fournisseur du modèle.",
    "provider_unavailable": "Le fournisseur du modèle est temporairement indisponible.",
    "provider_refused": "Le modèle a refusé cette demande. Reformulez votre question.",
    "clarification_expired": "Ce choix a expiré ou le serveur a redémarré. Relancez la question initiale.",
    "invalid_selection": "Ce choix n'est plus valide pour cette demande. Relancez la question initiale.",
    "invalid_refinement": "Cette précision ne figure pas dans les choix proposés.",
    "invalid_reference": "Choisissez un médicament proposé pour cette précision.",
    "session_expired": "Le contexte a expiré ou le serveur a redémarré. Ouvrez une nouvelle conversation et saisissez une question complète.",
    "invalid_request": "La demande est invalide. Saisissez entre 1 et 2 000 caractères.",
    "api_unreachable": "FastAPI est inaccessible. Vérifiez que le serveur est démarré.",
    "api_timeout": "FastAPI n'a pas répondu à temps. Vous pouvez réessayer manuellement.",
    "invalid_api_response": "La réponse de FastAPI est invalide. Vérifiez le serveur et sa version.",
    "api_error": "Le service a renvoyé une erreur. Aucune réponse n'a été substituée.",
}


@dataclass
class DemoError(Exception):
    code: str
    status: int | None = None
    retryable: bool = False
    retry_after_seconds: float | None = None

    @property
    def message(self):
        return ERROR_MESSAGES.get(self.code, ERROR_MESSAGES["api_error"])


def api_url(value: str | None = None) -> str:
    value = (value if value is not None else os.getenv("PHARMACY_API_URL", "http://127.0.0.1:8000")).strip().rstrip("/")
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or
        parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path):
        raise ValueError("PHARMACY_API_URL must be an HTTP(S) origin without credentials or a path")
    return value


class DemoClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = api_url(base_url)

    def _request(self, method: str, path: str, **kwargs):
        try:
            with requests.Session() as session:
                if urlsplit(self.base_url).hostname in {"localhost", "127.0.0.1", "::1"}:
                    session.trust_env = False
                response = session.request(method, self.base_url + path, **kwargs)
        except requests.Timeout:
            raise DemoError("api_timeout", retryable=True) from None
        except requests.RequestException:
            raise DemoError("api_unreachable", retryable=True) from None
        try:
            body = response.json()
        except ValueError:
            raise DemoError("invalid_api_response", response.status_code) from None
        if not response.ok:
            detail = body.get("detail", {}) if isinstance(body, dict) else {}
            detail = detail if isinstance(detail, dict) else {}
            code = detail.get("code", "invalid_request" if response.status_code == 422 else "api_error")
            if code not in ERROR_MESSAGES:
                code = "api_error"
            delay = detail.get("retry_after_seconds", response.headers.get("Retry-After"))
            try:
                delay = float(delay)
                if not math.isfinite(delay) or delay < 0:
                    delay = None
            except (ValueError, TypeError):
                delay = None
            retryable = detail.get("retryable")
            if not isinstance(retryable, bool):
                retryable = response.status_code in {429, 502, 503, 504}
            raise DemoError(code, response.status_code, retryable, delay)
        return body

    def health(self) -> HealthResponse:
        try:
            return HealthResponse.model_validate(self._request("GET", "/health", timeout=(2, 3)))
        except ValidationError:
            raise DemoError("invalid_api_response") from None

    def chat(self, payload: dict) -> ChatResponse:
        try:
            validated = ChatRequest.model_validate(payload)
        except ValidationError:
            raise DemoError("invalid_request", 422) from None
        body = self._request("POST", "/chat", json=validated.model_dump(exclude_none=True), timeout=(3, 175))
        try:
            return ChatResponse.model_validate(body)
        except ValidationError:
            raise DemoError("invalid_api_response") from None
