"""Short transactions around hosted inference; atomic success and sliding expiry."""

from contextlib import contextmanager
from datetime import timedelta
import hashlib
import json
import secrets
import uuid

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from pharmacy_assistant.contracts.storage import StorageUnavailable
from pharmacy_assistant.core.errors import ChatError
from pharmacy_assistant.core.storage import models as m


TTL = timedelta(minutes=30)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def public_payload(response):
    return response.model_dump(mode="json", exclude={"session_id", "continuation_id"})


class ConversationStore:
    def __init__(self, engine):
        self.engine = engine

    @contextmanager
    def transaction(self):
        try:
            with self.engine.begin() as db:
                yield db
        except (SQLAlchemyError, OSError):
            raise StorageUnavailable() from None

    def ready(self):
        """Check owned runtime tables without changing state or extending expiry."""
        with self.transaction() as db:
            db.execute(select(m.presentations.c.source_record_id).limit(1)).first()
            db.execute(select(m.conversations.c.id).limit(1)).first()

    def _create(self, db):
        now = db.scalar(select(func.clock_timestamp()))
        identifier = uuid.uuid4()
        row = dict(id=identifier, created_at=now, last_success_at=None, expires_at=now + TTL,
                   revision=0, next_sequence=0)
        db.execute(insert(m.conversations).values(**row))
        return row

    def _conversation(self, db, token, *, continuation=False):
        table = m.pending_choices if continuation else m.conversation_states
        state = db.execute(select(table).where(table.c.token_hash == token_hash(token))).mappings().first()
        error = "clarification_expired" if continuation else "session_expired"
        if state is None:
            raise ChatError(error, "Cette conversation ou ce choix a expiré. Commencez une nouvelle conversation.")
        parent = db.execute(select(m.conversations).where(m.conversations.c.id == state["conversation_id"]).with_for_update()).mappings().first()
        if parent is None or parent["expires_at"] <= db.scalar(select(func.clock_timestamp())):
            raise ChatError(error, "Cette conversation a expiré. Commencez une nouvelle conversation.")
        return dict(parent), dict(state)

    def _issue(self, db, parent, state_payload, choice_payload=None):
        now = db.scalar(select(func.clock_timestamp()))
        session = secrets.token_urlsafe(32)
        db.execute(insert(m.conversation_states).values(token_hash=token_hash(session), conversation_id=parent["id"],
            revision=parent["revision"], payload=state_payload, created_at=now))
        continuation = None
        if choice_payload is not None:
            continuation = secrets.token_urlsafe(32)
            db.execute(insert(m.pending_choices).values(token_hash=token_hash(continuation), conversation_id=parent["id"],
                revision=parent["revision"], payload=choice_payload, created_at=now))
        return session, continuation

    def create(self):
        with self.transaction() as db:
            parent = self._create(db)
            token, _ = self._issue(db, parent, {"version": 1, "state": None, "response": None})
            return dict(session_id=token, expires_at_utc=parent["expires_at"].isoformat(), messages=[], response=None)

    def begin(self, request):
        token = request.session_id or request.continuation_id
        if request.request_id and not token:
            raise ChatError("request_conflict", "Créez une conversation avant d'envoyer une demande avec request_id.")
        semantic = request.model_dump(mode="json", exclude={"session_id", "continuation_id", "request_id"})
        signature = hashlib.sha256(json.dumps(semantic, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.transaction() as db:
            if token:
                parent, state = self._conversation(db, token, continuation=bool(request.continuation_id))
            else:
                parent, state = self._create(db), None
            key = request.request_id or secrets.token_urlsafe(24)
            previous = db.execute(select(m.conversation_messages).where(
                m.conversation_messages.c.conversation_id == parent["id"],
                m.conversation_messages.c.request_key == key)).mappings().first()
            if previous:
                if previous["request_fingerprint"] != signature:
                    raise ChatError("request_conflict", "Cette référence de demande a déjà été utilisée pour un autre contenu.")
                if previous["outcome"] == "pending":
                    raise ChatError("request_in_progress", "Cette demande est déjà en cours. Ne la renvoyez pas automatiquement.")
                if previous["outcome"] == "answered" and previous["payload"]["revision"] == parent["revision"]:
                    return {"replay": self._view(db, parent)}
                raise ChatError("request_conflict", "Cette demande est terminée ou son résultat est incertain. Reprenez la conversation avant de réessayer.")
            if state and state["revision"] != parent["revision"]:
                raise ChatError("conversation_conflict", "La conversation a changé. Rechargez son dernier état.")
            identifier, now = uuid.uuid4(), db.scalar(select(func.clock_timestamp()))
            db.execute(insert(m.conversation_messages).values(id=identifier, conversation_id=parent["id"],
                sequence=parent["next_sequence"], role="user", outcome="pending", text=request.text,
                request_key=key, request_fingerprint=signature, created_at=now,
                payload={"action": semantic} if request.text is None else None))
            db.execute(update(m.conversations).where(m.conversations.c.id == parent["id"]).values(next_sequence=parent["next_sequence"] + 1))
            return dict(conversation_id=parent["id"], revision=parent["revision"], message_id=identifier,
                        state=state["payload"] if state else None, continuation=bool(request.continuation_id), action=semantic)

    def fail(self, turn, code):
        with self.transaction() as db:
            db.execute(update(m.conversation_messages).where(m.conversation_messages.c.id == turn["message_id"],
                m.conversation_messages.c.outcome == "pending").values(outcome="failed", payload={"error_code": code}))

    def complete(self, turn, response, state_payload, choice_payload):
        with self.transaction() as db:
            parent = db.execute(select(m.conversations).where(m.conversations.c.id == turn["conversation_id"]).with_for_update()).mappings().first()
            now = db.scalar(select(func.clock_timestamp()))
            if parent is None or parent["expires_at"] <= now:
                raise ChatError("session_expired", "Cette conversation a expiré pendant la demande.")
            if parent["revision"] != turn["revision"]:
                raise ChatError("conversation_conflict", "Une autre demande a modifié la conversation. Rechargez son dernier état.")
            parent = {**parent, "revision": parent["revision"] + 1, "expires_at": now + TTL}
            payload = {"version": 1, "state": state_payload, "response": public_payload(response)}
            session, continuation = self._issue(db, parent, payload, choice_payload)
            db.execute(insert(m.conversation_messages).values(id=uuid.uuid4(), conversation_id=parent["id"],
                sequence=parent["next_sequence"], role="assistant", outcome="answered", text=response.answer,
                payload=public_payload(response), created_at=now))
            db.execute(update(m.conversation_messages).where(m.conversation_messages.c.id == turn["message_id"]).values(
                outcome="answered", payload={"revision": parent["revision"], "action": turn["action"]}))
            db.execute(update(m.conversations).where(m.conversations.c.id == parent["id"]).values(
                revision=parent["revision"], expires_at=parent["expires_at"], last_success_at=now,
                next_sequence=parent["next_sequence"] + 1))
            expiry = parent["expires_at"].isoformat()
            return response.model_copy(update=dict(session_id=session, continuation_id=continuation,
                session_expires_at_utc=expiry, continuation_expires_at_utc=expiry if continuation else None))

    def _view(self, db, parent):
        # A crashed worker cannot finish an old pending turn. Do not retry it or
        # advance context automatically; preserve it as an uncertain failure.
        db.execute(update(m.conversation_messages).where(
            m.conversation_messages.c.conversation_id == parent["id"],
            m.conversation_messages.c.outcome == "pending",
            m.conversation_messages.c.created_at < func.clock_timestamp() - timedelta(minutes=3)
        ).values(outcome="failed", payload={"error_code": "completion_unknown"}))
        latest = db.execute(select(m.conversation_states).where(m.conversation_states.c.conversation_id == parent["id"],
            m.conversation_states.c.revision == parent["revision"]).order_by(m.conversation_states.c.created_at.desc()).limit(1)).mappings().one()
        choice = db.execute(select(m.pending_choices).where(m.pending_choices.c.conversation_id == parent["id"],
            m.pending_choices.c.revision == parent["revision"]).limit(1)).mappings().first()
        session, continuation = self._issue(db, parent, latest["payload"], choice["payload"] if choice else None)
        expiry = parent["expires_at"].isoformat()
        result = latest["payload"]["response"]
        if result is not None:
            result = {**result, "session_id": session, "continuation_id": continuation,
                      "session_expires_at_utc": expiry, "continuation_expires_at_utc": expiry if continuation else None,
                      "inference_performed": False}
        messages = [dict(sequence=row["sequence"], role=row["role"], outcome=row["outcome"], text=row["text"],
                         created_at_utc=row["created_at"].isoformat(), payload=row["payload"])
                    for row in db.execute(select(m.conversation_messages).where(m.conversation_messages.c.conversation_id == parent["id"]).order_by(m.conversation_messages.c.sequence)).mappings()]
        return dict(session_id=session, expires_at_utc=expiry, messages=messages, response=result)

    def restore(self, token):
        with self.transaction() as db:
            parent, _ = self._conversation(db, token)
            return self._view(db, parent)

    def reset(self, token):
        with self.transaction() as db:
            parent, _ = self._conversation(db, token)
            db.execute(delete(m.conversations).where(m.conversations.c.id == parent["id"]))

    def cleanup(self):
        with self.transaction() as db:
            result = db.execute(delete(m.conversations).where(m.conversations.c.expires_at <= func.clock_timestamp()))
            return result.rowcount
