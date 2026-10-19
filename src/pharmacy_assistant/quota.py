"""Cross-process request spacing, cooldowns and durable evaluation budgets.

Only local counters/timestamps and provider/model identifiers are stored. No
keys, prompts, patient text or responses enter this database.
"""

import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, time as day_time, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pharmacy_assistant.config import Settings
from pharmacy_assistant.nlu_models import InferenceError


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


class QuotaStore:
    def __init__(self, path: Path, *, clock=time.time):
        self.path = Path(path)
        self.clock = clock

    @contextmanager
    def connection(self):
        connection = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=5)
            connection.execute("""CREATE TABLE IF NOT EXISTS quota_state (
                scope TEXT PRIMARY KEY, next_at REAL NOT NULL DEFAULT 0,
                blocked_until REAL NOT NULL DEFAULT 0, block_code TEXT,
                attempts INTEGER NOT NULL DEFAULT 0)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS evaluation_budgets (
                id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL,
                maximum INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0)""")
            yield connection
        except (OSError, sqlite3.Error):
            raise InferenceError("quota_state_unavailable", "Local quota state is unavailable. Further provider requests are blocked.", 503) from None
        finally:
            if connection is not None:
                connection.close()

    def new_budget(self, budget_id: str, evaluation_id: str, maximum: int):
        if maximum < 0:
            raise ValueError("Request budget must be non-negative")
        with self.connection() as db, db:
            db.execute("INSERT INTO evaluation_budgets (id, evaluation_id, maximum) VALUES (?, ?, ?)",
                       (budget_id, evaluation_id, maximum))

    def budget_counts(self, budget_id: str, evaluation_id: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT maximum, used FROM evaluation_budgets WHERE id=? AND evaluation_id=?", (budget_id, evaluation_id)).fetchone()
            total = db.execute("SELECT COALESCE(SUM(used), 0) FROM evaluation_budgets WHERE evaluation_id=?", (evaluation_id,)).fetchone()[0]
        if row is None:
            raise InferenceError("quota_state_unavailable", "This report's request ledger is missing. No provider request was sent.", 503)
        return {"max_requests": row[0], "attempts_reserved": row[1], "total_attempts_reserved": total}

    def reserve(self, scope: str, interval: float, budget_id: str | None = None):
        with self.connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            if budget_id is not None:
                budget = db.execute("SELECT maximum, used FROM evaluation_budgets WHERE id=?", (budget_id,)).fetchone()
                if budget is None:
                    raise InferenceError("quota_state_unavailable", "The evaluation budget is unavailable. No provider request was sent.", 503)
                if budget[1] >= budget[0]:
                    raise InferenceError("evaluation_budget_exhausted", "This invocation's provider request budget has been reached. Resume with a new explicit budget.", 429)
            now = self.clock()
            row = db.execute("SELECT next_at, blocked_until, block_code FROM quota_state WHERE scope=?", (scope,)).fetchone()
            if row is not None:
                if row[1] > now:
                    raise InferenceError(row[2] or "provider_rate_limited", "A shared provider cooldown is active. No provider request was sent.",
                                         429, row[2] != "provider_daily_quota_exhausted", row[1] - now)
                if interval > 0 and row[0] > now:
                    raise InferenceError("local_rate_limited", "Local request spacing is active. Retry after the indicated delay.", 429, True, row[0] - now)
            db.execute("""INSERT INTO quota_state (scope, next_at, attempts) VALUES (?, ?, 1)
                ON CONFLICT(scope) DO UPDATE SET next_at=excluded.next_at, attempts=attempts+1""", (scope, now + interval))
            if budget_id is not None:
                db.execute("UPDATE evaluation_budgets SET used=used+1 WHERE id=?", (budget_id,))

    def cooldown(self, scope: str, seconds: float, code: str):
        with self.connection() as db, db:
            db.execute("""INSERT INTO quota_state (scope, blocked_until, block_code) VALUES (?, ?, ?)
                ON CONFLICT(scope) DO UPDATE SET
                block_code=CASE WHEN excluded.blocked_until >= blocked_until THEN excluded.block_code ELSE block_code END,
                blocked_until=MAX(blocked_until, excluded.blocked_until)""", (scope, self.clock() + seconds, code))

    def status(self, scope: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT next_at, blocked_until, block_code, attempts FROM quota_state WHERE scope=?", (scope,)).fetchone()
        now = self.clock()
        return {"scope": scope, "local_attempts_reserved": row[3] if row else 0,
                "spacing_remaining_seconds": round(max(0, row[0] - now), 2) if row else 0,
                "cooldown_remaining_seconds": round(max(0, row[1] - now), 2) if row else 0,
                "cooldown_code": row[2] if row and row[1] > now else None}


class AttemptControl:
    def __init__(self, store: QuotaStore, scope: str, interval: float, *,
                 budget_id: str | None = None, wait: bool = False, sleep=asyncio.sleep):
        self.store, self.scope, self.interval = store, scope, interval
        self.budget_id, self.wait, self.sleep = budget_id, wait, sleep

    @classmethod
    def from_settings(cls, settings: Settings, **kwargs):
        return cls(QuotaStore(settings.inference_quota_db),
                   f"{settings.inference_quota_scope}:{settings.inference_provider}:{settings.inference_model}",
                   settings.inference_min_interval_seconds, **kwargs)

    async def before_attempt(self):
        waited = 0
        while True:
            try:
                self.store.reserve(self.scope, self.interval, self.budget_id)
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


def main():
    parser = argparse.ArgumentParser(description="Show local inference spacing and cooldowns; sends no model requests.")
    parser.parse_args()
    control = AttemptControl.from_settings(Settings.from_env())
    print(json.dumps(control.store.status(control.scope), indent=2))


if __name__ == "__main__":
    main()
