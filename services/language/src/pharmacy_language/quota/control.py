"""Cross-process request spacing, cooldowns and durable evaluation budgets.

Only local counters/timestamps and provider/model identifiers are stored. No
keys, prompts, patient text or responses enter this database.
"""

import asyncio
from datetime import datetime, time as day_time, timedelta, timezone
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pharmacy_language.config import LanguageSettings as Settings
from pharmacy_contracts.interpretation import InferenceError


def daily_reset_delay(now: float | None = None) -> float:
    """Google's daily reset is midnight Pacific; fail conservatively without tzdata."""
    now = time.time() if now is None else now
    try:
        zone = ZoneInfo("America/Los_Angeles")
    except ZoneInfoNotFoundError:
        return 86400
    local = datetime.fromtimestamp(now, zone)
    midnight = datetime.combine(local.date() + timedelta(days=1), day_time(), tzinfo=zone)
    return max(1, midnight.timestamp() - now)


class AttemptControl:
    def __init__(self, store, scope: str, interval: float, *,
                 budget_id: str | None = None, wait: bool = False, sleep=asyncio.sleep):
        self.store, self.scope, self.interval = store, scope, interval
        self.budget_id, self.wait, self.sleep = budget_id, wait, sleep

    @classmethod
    def from_settings(cls, settings: Settings, **kwargs):
        from pharmacy_infrastructure.database import create_database_engine
        from pharmacy_language.storage.postgres.quota import PostgresQuotaStore
        store = PostgresQuotaStore(create_database_engine(settings.language_database_url.get_secret_value()))
        return cls(store,
                   f"{settings.inference_quota_scope}:{settings.inference_provider}:{settings.inference_model}",
                   settings.inference_min_interval_seconds, **kwargs)

    async def before_attempt(self):
        waited = 0
        while True:
            try:
                await asyncio.to_thread(self.store.reserve, self.scope, self.interval, self.budget_id)
                return
            except InferenceError as error:
                delay = error.detail.retry_after_seconds or 0
                if not self.wait or error.detail.code != "local_rate_limited" or waited + delay > 60:
                    raise
                await self.sleep(max(0.01, delay))
                waited += max(0.01, delay)

    def failed(self, error: InferenceError) -> InferenceError:
        if error.detail.code in {"provider_rate_limited", "provider_daily_quota_exhausted"}:
            delay = error.detail.retry_after_seconds
            if delay is None:
                delay = 60  # No advertised cooldown: avoid repeatedly probing.
            delay = max(1, delay)
            self.store.cooldown(self.scope, delay, error.detail.code)
            return InferenceError(error.detail.code, error.detail.message, error.status_code,
                                  error.detail.retryable, delay)
        return error

    def close(self):
        if hasattr(self.store, "engine"):
            self.store.engine.dispose()
