from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

from .logging_config import get_logger
from .models import WorkflowEvent

logger = get_logger("workflow")


class WorkflowTracker:
    def __init__(self) -> None:
        self._events: list[WorkflowEvent] = []

    @property
    def events(self) -> tuple[WorkflowEvent, ...]:
        return tuple(self._events)

    def add(
        self,
        step: str,
        message: str,
        duration_ms: float | None = None,
    ) -> WorkflowEvent:
        event = WorkflowEvent(
            step=step,
            message=message,
            duration_ms=duration_ms,
        )
        self._events.append(event)
        suffix = (
            f" ({duration_ms:.0f} ms)"
            if duration_ms is not None
            else ""
        )
        logger.info("[%s] %s%s", step, message, suffix)
        return event

    @contextmanager
    def timed(
        self,
        step: str,
        start_message: str,
        done_message: str | None = None,
    ) -> Iterator[None]:
        self.add(step, start_message)
        start = perf_counter()
        try:
            yield
        except Exception:
            duration = (perf_counter() - start) * 1000
            self.add(step, f"{start_message} failed", duration)
            raise
        else:
            duration = (perf_counter() - start) * 1000
            self.add(
                step,
                done_message or f"{start_message} completed",
                duration,
            )

    def clear(self) -> None:
        self._events.clear()
