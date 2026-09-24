"""Bounded attention records carried by the managed Lead lease.

These records describe questions and possible stalls. They never confer
authority or change the room's lifecycle, assignment or Human decision.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

MAX_ASKS_PER_LEASE = 256
MAX_OPEN_ASKS = 64
MAX_ASK_ID = 120
MAX_QUESTION = 2000
MAX_ANSWER = 4000
REMIND_AFTER = dt.timedelta(minutes=30)
ESCALATE_AFTER = dt.timedelta(hours=2)


class AttentionError(ValueError):
    pass


def bounded_text(value: Any, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise AttentionError(f"{label} must be non-empty and at most {limit} characters")
    return value.strip()


def asks_for(lease: dict[str, Any]) -> dict[str, dict[str, Any]]:
    asks = lease.get("room_asks", {})
    if not isinstance(asks, dict) or len(asks) > MAX_ASKS_PER_LEASE:
        raise AttentionError("managed room ask queue is invalid or over capacity")
    for ask_id, item in asks.items():
        if (
            not isinstance(ask_id, str)
            or not ask_id or len(ask_id) > MAX_ASK_ID
            or not isinstance(item, dict)
            or item.get("ask_id") != ask_id
            or item.get("status") not in {"OPEN", "ANSWERED"}
            or type(item.get("work_epoch")) is not int
            or item["work_epoch"] < 1
            or not isinstance(item.get("question"), str)
            or not isinstance(item.get("sender_agent_id"), str)
            or item.get("sender_role") not in {"lead", "peer"}
            or not isinstance(item.get("recipient_agent_id"), str)
            or not isinstance(item.get("created_at"), str)
            or (item["status"] == "ANSWERED" and (
                not isinstance(item.get("answer"), str)
                or not isinstance(item.get("answered_by"), str)
                or not isinstance(item.get("answered_at"), str)
            ))
        ):
            raise AttentionError("managed room ask queue contains an invalid record")
    return asks


def open_ask(
    lease: dict[str, Any], *, ask_id: str, question: str, sender: str,
    sender_role: str, recipient: str, work_epoch: int, created_at: str,
) -> tuple[dict[str, Any], bool]:
    ask_id = bounded_text(ask_id, "askId", MAX_ASK_ID)
    question = bounded_text(question, "question", MAX_QUESTION)
    if type(work_epoch) is not int or work_epoch < 1:
        raise AttentionError("ask epoch is invalid")
    asks = asks_for(lease)
    existing = asks.get(ask_id)
    if existing is not None:
        if any(existing.get(key) != value for key, value in {
            "question": question, "sender_agent_id": sender,
            "recipient_agent_id": recipient, "work_epoch": work_epoch,
        }.items()):
            raise AttentionError("ask identity already binds different evidence")
        return existing, False
    if len(asks) >= MAX_ASKS_PER_LEASE or sum(
        item["status"] == "OPEN" for item in asks.values()
    ) >= MAX_OPEN_ASKS:
        raise AttentionError("managed room ask queue is at capacity")
    item = {
        "ask_id": ask_id, "question": question, "sender_agent_id": sender,
        "sender_role": sender_role,
        "recipient_agent_id": recipient, "work_epoch": work_epoch,
        "created_at": created_at, "status": "OPEN",
    }
    lease.setdefault("room_asks", asks)[ask_id] = item
    return item, True


def answer_ask(
    lease: dict[str, Any], *, ask_id: str, answer: str, actor: str,
    work_epoch: int, answered_at: str,
) -> tuple[dict[str, Any], bool]:
    ask_id = bounded_text(ask_id, "askId", MAX_ASK_ID)
    answer = bounded_text(answer, "answer", MAX_ANSWER)
    item = asks_for(lease).get(ask_id)
    if item is None or item.get("work_epoch") != work_epoch:
        raise AttentionError("ask is absent or belongs to a different work epoch")
    if item.get("recipient_agent_id") != actor:
        raise AttentionError("only the responsible recipient may answer this ask")
    if item["status"] == "ANSWERED":
        if item.get("answer") != answer or item.get("answered_by") != actor:
            raise AttentionError("ask was already answered with different evidence")
        return item, False
    item.update(status="ANSWERED", answer=answer, answered_by=actor, answered_at=answered_at)
    return item, True


def attention_for(item: dict[str, Any], now: dt.datetime, *, has_supervisor: bool) -> dict[str, Any]:
    view = dict(item)
    view["attention"] = None
    view["escalate_to"] = None
    if item["status"] != "OPEN":
        return view
    try:
        created = dt.datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as error:
        raise AttentionError("ask timestamp is invalid") from error
    if created.tzinfo is None:
        raise AttentionError("ask timestamp must include a timezone")
    elapsed = max(dt.timedelta(), now - created)
    if elapsed >= ESCALATE_AFTER:
        view["attention"] = "ESCALATE"
        view["escalate_to"] = "supervisor" if item.get("sender_role") == "peer" and has_supervisor else "human"
    elif elapsed >= REMIND_AFTER:
        view["attention"] = "REMIND"
    return view


def peer_turn_signal(
    status_payload: dict[str, Any], activity_payload: dict[str, Any],
    *, has_terminal_handback: bool,
) -> str | None:
    """Report suspicion only; native idle is never proof of completion."""
    status = status_payload.get("status")
    snapshot = status_payload.get("snapshot")
    pending = snapshot.get("pendingPermissions") if isinstance(snapshot, dict) else None
    if isinstance(pending, list) and pending:
        return "PENDING_PERMISSION"
    if status in {"closed", "error"} and not has_terminal_handback:
        return "TERMINAL_WITHOUT_HANDBACK"
    update_count = activity_payload.get("updateCount")
    content = activity_payload.get("content")
    if (
        status == "idle" and not has_terminal_handback
        and type(update_count) is int and update_count > 0
        and isinstance(content, str) and content.strip()
    ):
        return "POSSIBLE_MISSING_HANDBACK"
    return None
