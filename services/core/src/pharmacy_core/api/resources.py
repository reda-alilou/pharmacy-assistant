"""Explicit dependency injection for offline fixtures; no runtime storage switch."""
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from pharmacy_contracts.interpreter import Interpreter
from pharmacy_core.medications.catalog import MedicationCatalog
from pharmacy_core.pharmacies.directory import PharmacyDirectory
from pharmacy_core.conversation.models import ChatRequest, ChatResponse

if TYPE_CHECKING:
    from pharmacy_core.storage.postgres.conversations import ConversationStore


class ChatResponder(Protocol):
    async def respond(self, request: ChatRequest) -> ChatResponse: ...


@dataclass
class CoreResources:
    catalog: MedicationCatalog
    directory: PharmacyDirectory
    interpreter: Interpreter
    chat: ChatResponder
    conversations: 'ConversationStore | None' = None
