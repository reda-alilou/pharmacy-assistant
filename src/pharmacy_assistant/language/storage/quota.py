"""PostgreSQL attempt reservations, cooldowns, and durable evaluation budgets."""

from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sqlite3

from sqlalchemy import case, func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from pharmacy_assistant.contracts.nlu_models import InferenceError
from pharmacy_assistant.language.storage.models import evaluation_budgets as budgets, quota_state as states, quota_imports


EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class PostgresQuotaStore:
    def __init__(self, engine, *, clock=None):
        self.engine, self.clock = engine, clock

    @contextmanager
    def connection(self):
        try:
            with self.engine.begin() as connection:
                yield connection
        except (SQLAlchemyError, OSError):
            raise InferenceError("quota_state_unavailable", "Le suivi du quota est indisponible. Aucun nouvel appel au modèle n'est autorisé.", 503) from None

    def now(self, db):
        return datetime.fromtimestamp(self.clock(), timezone.utc) if self.clock else db.scalar(select(func.clock_timestamp()))

    def new_budget(self, budget_id, evaluation_id, maximum):
        if maximum < 0:
            raise ValueError("Request budget must be non-negative")
        with self.connection() as db:
            db.execute(insert(budgets).values(id=budget_id, evaluation_id=evaluation_id, maximum=maximum, used=0))

    def budget_counts(self, budget_id, evaluation_id):
        with self.connection() as db:
            row = db.execute(select(budgets).where(budgets.c.id == budget_id, budgets.c.evaluation_id == evaluation_id)).mappings().first()
            if not row:
                raise InferenceError("quota_state_unavailable", "The evaluation ledger is missing. No provider request was sent.", 503)
            total = db.scalar(select(func.coalesce(func.sum(budgets.c.used), 0)).where(budgets.c.evaluation_id == evaluation_id))
            return dict(max_requests=row["maximum"], attempts_reserved=row["used"], total_attempts_reserved=total)

    def reserve(self, scope, interval, budget_id=None):
        with self.connection() as db:
            if budget_id is not None:
                budget = db.execute(select(budgets).where(budgets.c.id == budget_id).with_for_update()).mappings().first()
                if not budget:
                    raise InferenceError("quota_state_unavailable", "The evaluation budget is unavailable. No provider request was sent.", 503)
                if budget["used"] >= budget["maximum"]:
                    raise InferenceError("evaluation_budget_exhausted", "This invocation's provider request budget has been reached.", 429)
            db.execute(pg_insert(states).values(scope=scope, next_at=EPOCH, blocked_until=EPOCH, attempts=0).on_conflict_do_nothing())
            row = db.execute(select(states).where(states.c.scope == scope).with_for_update()).mappings().one()
            now = self.now(db)
            if row["blocked_until"] > now:
                code = row["block_code"] or "provider_rate_limited"
                raise InferenceError(code, "A shared provider cooldown is active. No provider request was sent.",
                                     429, code != "provider_daily_quota_exhausted", (row["blocked_until"] - now).total_seconds())
            if interval > 0 and row["next_at"] > now:
                raise InferenceError("local_rate_limited", "Local request spacing is active.", 429, True, (row["next_at"] - now).total_seconds())
            db.execute(update(states).where(states.c.scope == scope).values(next_at=now + timedelta(seconds=interval), attempts=states.c.attempts + 1))
            if budget_id is not None:
                db.execute(update(budgets).where(budgets.c.id == budget_id).values(used=budgets.c.used + 1))

    def cooldown(self, scope, seconds, code):
        with self.connection() as db:
            deadline = self.now(db) + timedelta(seconds=seconds)
            statement = pg_insert(states).values(scope=scope, next_at=EPOCH, blocked_until=deadline, block_code=code, attempts=0)
            db.execute(statement.on_conflict_do_update(index_elements=[states.c.scope], set_={
                "blocked_until": func.greatest(states.c.blocked_until, statement.excluded.blocked_until),
                "block_code": case((statement.excluded.blocked_until >= states.c.blocked_until, code), else_=states.c.block_code)}))

    def status(self, scope):
        with self.connection() as db:
            row = db.execute(select(states).where(states.c.scope == scope)).mappings().first()
            now = self.now(db)
            return dict(scope=scope, local_attempts_reserved=row["attempts"] if row else 0,
                spacing_remaining_seconds=round(max(0, (row["next_at"] - now).total_seconds()), 2) if row else 0,
                cooldown_remaining_seconds=round(max(0, (row["blocked_until"] - now).total_seconds()), 2) if row else 0,
                cooldown_code=row["block_code"] if row and row["blocked_until"] > now else None)

    def import_sqlite(self, path):
        path = Path(path).resolve()
        if not path.is_file():
            raise ValueError("The original quota ledger is missing.")
        # SQLite backup includes committed WAL data, without modifying the source.
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as original:
            snapshot = sqlite3.connect(":memory:")
            try:
                original.backup(snapshot)
                rows = snapshot.execute("SELECT scope,next_at,blocked_until,block_code,attempts FROM quota_state ORDER BY scope").fetchall()
            finally:
                snapshot.close()
        import json
        signature = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
        with self.connection() as db:
            db.execute(text("SELECT pg_advisory_xact_lock(719942002)"))
            if db.scalar(select(quota_imports.c.input_hash).where(quota_imports.c.input_hash == signature)):
                return {"repeated": True, "scopes": len(rows)}
            for scope, next_at, blocked, code, attempts in rows:
                statement = pg_insert(states).values(scope=scope,
                    next_at=datetime.fromtimestamp(next_at, timezone.utc), blocked_until=datetime.fromtimestamp(blocked, timezone.utc),
                    block_code=code, attempts=attempts)
                db.execute(statement.on_conflict_do_update(index_elements=[states.c.scope], set_={
                    "next_at": func.greatest(states.c.next_at, statement.excluded.next_at),
                    "blocked_until": func.greatest(states.c.blocked_until, statement.excluded.blocked_until),
                    "attempts": func.greatest(states.c.attempts, statement.excluded.attempts),
                    "block_code": case((statement.excluded.blocked_until >= states.c.blocked_until, statement.excluded.block_code), else_=states.c.block_code)}))
            db.execute(insert(quota_imports).values(input_hash=signature, source_path=str(path), imported_at=self.now(db)))
        return {"repeated": False, "scopes": len(rows), "historical_budgets_imported": False}
