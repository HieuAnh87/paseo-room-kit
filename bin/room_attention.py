"""Bounded attention records carried by the managed Lead lease.

These records describe questions and possible stalls. They never confer
authority or change the room's lifecycle, assignment or Human decision.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

MAX_ASKS_PER_LEASE = 256
MAX_OPEN_ASKS = 64
MAX_ASK_ID = 120
MAX_QUESTION = 2000
MAX_ANSWER = 4000
RESOLUTION_OUTCOMES = {"RESOLVED_BY_LEAD", "NEEDS_MORE_EVIDENCE", "ESCALATED_TO_HUMAN"}
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
        if "resolution" in item:
            resolution = item["resolution"]
            if (not isinstance(resolution, dict)
                or resolution.get("outcome") not in RESOLUTION_OUTCOMES
                or any(not isinstance(resolution.get(key), str) or not resolution[key].strip()
                       for key in ("decision", "evidence", "nextAction"))
                or type(resolution.get("changesWork")) is not bool
                or not isinstance(resolution.get("resolved_by"), str)):
                raise AttentionError("managed room ask has an invalid resolution")
            if (item.get("kind") != "REOPEN_REQUEST"
                or (resolution["outcome"] == "RESOLVED_BY_LEAD") != (item["status"] == "ANSWERED")):
                raise AttentionError("managed room resolution state is inconsistent")
            if resolution["outcome"] != "RESOLVED_BY_LEAD" and any(
                not isinstance(resolution.get(key), str) or not resolution[key].strip()
                for key in ("owner", "checkpoint")
            ):
                raise AttentionError("pending resolution requires owner and checkpoint")
            if resolution["changesWork"] and not isinstance(resolution.get("candidateDigest"), str):
                raise AttentionError("changed-work resolution requires candidate evidence")
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
    if item.get("kind") == "REOPEN_REQUEST":
        raise AttentionError("REOPEN_REQUEST needs resolve_peer_report with decision and evidence")
    if item["status"] == "ANSWERED":
        if item.get("answer") != answer or item.get("answered_by") != actor:
            raise AttentionError("ask was already answered with different evidence")
        return item, False
    item.update(status="ANSWERED", answer=answer, answered_by=actor, answered_at=answered_at)
    return item, True


def reopen_obligations(lease: dict[str, Any]) -> list[dict[str, Any]]:
    asks = asks_for(lease)
    obligations = [item for item in asks.values() if item["work_epoch"] == lease["work_epoch"]
                   and item.get("kind") == "REOPEN_REQUEST" and item["status"] == "OPEN"]
    # Reports recorded before this feature still raise an obligation. Never infer
    # closure merely because the old writer did not create an ask.
    for report_id, receipt in reports_for(lease).items():
        report = receipt["report"]
        if report.get("workEpoch") == lease["work_epoch"] and report.get("kind") == "REOPEN_REQUEST" and "peer:" + report_id not in asks:
            obligations.append({"report_id": report_id, "status": "OPEN", "resolution": {}})
    return obligations


def reports_for(lease: dict[str, Any]) -> dict[str, Any]:
    reports = lease.get("peer_reports", {})
    if not isinstance(reports, dict) or any(
        not isinstance(key, str) or not isinstance(receipt, dict) or not isinstance(receipt.get("report"), dict)
        for key, receipt in reports.items()
    ):
        raise AttentionError("room report receipt is invalid")
    return reports


def observations_for(lease: dict[str, Any]) -> dict[str, Any]:
    """Join explicit receipts only. Missing evidence is unknown, never misconduct."""
    reports = reports_for(lease)
    briefs = lease.get("peer_briefs", {})
    if not isinstance(reports, dict) or not isinstance(briefs, dict):
        raise AttentionError("room observation evidence is invalid")
    asks = asks_for(lease)
    observations = []
    current = []
    for report_id, receipt in reports.items():
        if not isinstance(receipt, dict) or not isinstance(receipt.get("report"), dict):
            raise AttentionError("room report receipt is invalid")
        report = receipt["report"]
        if report.get("workEpoch") == lease["work_epoch"]:
            current.append((report_id, receipt))
    current.sort(key=lambda pair: (str(pair[1].get("recorded_at", "")), pair[0]))
    for report_id, receipt in current[-64:]:
        report = receipt["report"]
        brief = briefs.get(report.get("peerAgentId"))
        if not isinstance(brief, dict) or brief.get("assignment_id") != report.get("assignmentId") or brief.get("work_epoch") != report.get("workEpoch"):
            brief = None
        ask = asks.get(receipt.get("ask_id"))
        handling = "UNKNOWN"
        if ask:
            resolution = ask.get("resolution")
            handling = (resolution["outcome"] if resolution else
                        "ANSWERED" if ask["status"] == "ANSWERED" else "PENDING")
        elif report.get("kind") == "REOPEN_REQUEST":
            handling = "PENDING"  # Legacy receipt still has an unresolved obligation.
        handback = json.dumps(report.get("payload"), ensure_ascii=False, sort_keys=True)
        observations.append({
            "report_id": report_id, "peer_agent_id": report.get("peerAgentId"),
            "assignment_id": report.get("assignmentId"), "kind": report.get("kind"),
            "brief": brief, "brief_visibility": "OBSERVED" if brief else "UNKNOWN",
            "handback": report.get("payload") if len(handback) <= 4000 else None,
            "handback_excerpt": handback[:4000], "handback_truncated": len(handback) > 4000,
            "report_digest": receipt.get("digest"),
            "recorded_at": receipt.get("recorded_at"), "handling": handling,
            "ask": ask,
        })
    grants = lease.get("peer_steering", {})
    if not isinstance(grants, dict):
        raise AttentionError("room steering evidence is invalid")
    return {"observations": observations, "omitted_reports": max(0, len(current) - 64),
            "steering": [dict(item, grant_id=key) for key, item in grants.items()
                         if isinstance(item, dict) and item.get("work_epoch") == lease["work_epoch"]],
            "interpretation": "Explicit communication evidence only; UNKNOWN is not a violation. No artifact, reasoning, or acceptance verdict is inferred."}


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
