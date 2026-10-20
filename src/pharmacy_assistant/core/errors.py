"""Conversation failures expressed without HTTP or provider dependencies."""

from typing import Literal


ChatErrorCode = Literal[
    "session_expired", "clarification_expired", "invalid_reference",
    "invalid_selection", "invalid_refinement",
    "conversation_conflict", "request_in_progress", "request_conflict",
]


class ChatError(Exception):
    def __init__(self, code: ChatErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
