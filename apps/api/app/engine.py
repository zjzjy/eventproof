"""Pure event evolution engine.

The engine intentionally has no database or network dependencies. It takes an
event snapshot and a new document, then returns the next event, a revision,
and an optional notification. This keeps the same-event rules testable before
they are wired into ingestion.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


STAGE_ACTIONS = {"sign", "close", "terminate", "approve"}
CORE_SLOTS = {"actor", "target", "action"}


def now_utc(value: str | None = None) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _claim(event: dict[str, Any], claim_id: str | None) -> dict[str, Any] | None:
    if not claim_id:
        return None
    return next((item for item in event.get("claims", []) if item.get("id") == claim_id), None)


def _status(claim: dict[str, Any]) -> str:
    return claim.get("status") or "active"


def match_event(document: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """Match a document to an event using explicit refs first, then key slots."""
    refs = set(document.get("refs") or [])
    slots = document.get("slots") or {}
    for event in events:
        event_slots = event.get("slots") or {}
        explicit = event.get("id") in refs or document.get("id") in (event.get("source_doc_ids") or [])
        shared = {key: value for key, value in slots.items() if event_slots.get(key) == value}
        differences = [
            key
            for key, value in slots.items()
            if key in event_slots and event_slots.get(key) != value
        ]

        if explicit:
            if document.get("stage") in STAGE_ACTIONS:
                return {
                    "decision": "link",
                    "relation": "follow_up",
                    "score": 0.97,
                    "shared_slots": shared,
                    "differences": differences,
                    "reason": "显式引用原事件，但属于同一 Storyline 的下一阶段。",
                }
            return {
                "decision": "merge",
                "relation": "update",
                "score": 0.98,
                "shared_slots": shared,
                "differences": differences,
                "reason": "文档显式引用原事件；按同一事件处理。",
            }

        same_actor = slots.get("actor") and slots.get("actor") == event_slots.get("actor")
        same_action = slots.get("action") and slots.get("action") == event_slots.get("action")
        same_target = slots.get("target") and slots.get("target") == event_slots.get("target")

        if slots.get("target") and event_slots.get("target") and slots.get("target") != event_slots.get("target"):
            return {
                "decision": "link",
                "relation": "related",
                "score": 0.25,
                "shared_slots": shared,
                "differences": differences,
                "reason": "同一主体但标的/对象不同；只建立相关关系，不合并。",
            }

        if same_actor and same_action and same_target and not differences:
            return {
                "decision": "merge",
                "relation": "update",
                "score": 0.86,
                "shared_slots": shared,
                "differences": differences,
                "reason": "主体、动作、标的槽位一致；候选合并。",
            }

        if same_actor and differences:
            return {
                "decision": "review",
                "relation": "update",
                "score": 0.58,
                "shared_slots": shared,
                "differences": differences,
                "reason": "同一主体但关键槽位冲突；不自动合并。",
            }

        if same_actor:
            return {
                "decision": "link",
                "relation": "related",
                "score": 0.35,
                "shared_slots": shared,
                "differences": differences,
                "reason": "同一主体但命题不同；只建立相关关系。",
            }

    return {
        "decision": "new",
        "relation": "new",
        "score": 0.0,
        "shared_slots": {},
        "differences": [],
        "reason": "没有命中同一事件的显式引用或关键槽位。",
    }


def infer_change_type(document: dict[str, Any]) -> str:
    claim_types = {claim.get("claim_type") for claim in document.get("claims", [])}
    if document.get("conflict") or any(claim.get("conflict") for claim in document.get("claims", [])):
        return "conflict"
    if "denial" in claim_types:
        return "denial"
    if "correction" in claim_types:
        return "correction"
    if document.get("stage") in STAGE_ACTIONS:
        return "new_stage"
    if "rumor" in claim_types:
        return "rumor"
    return "update"


def derive_status(claims: list[dict[str, Any]]) -> dict[str, str]:
    core_claims = [claim for claim in claims if claim.get("claim_role") == "acquisition_fact"]
    if any(_status(claim) == "denied" for claim in core_claims):
        core = "denied"
    elif _has_slot_conflict(core_claims):
        core = "disputed"
    elif any(
        _status(claim) == "active" and claim.get("claim_type") in {"fact", "correction"}
        for claim in core_claims
    ):
        core = "confirmed"
    else:
        core = "unverified"

    rumors = [claim for claim in claims if claim.get("claim_type") == "rumor"]
    if rumors and any(_status(claim) == "denied" for claim in rumors):
        narrative = "denied"
    elif rumors:
        narrative = "unverified"
    else:
        narrative = "none"

    impact = (
        "observed"
        if any(claim.get("claim_role") == "market_reaction" for claim in claims)
        else "unverified"
    )
    return {"core": core, "narrative": narrative, "impact": impact}


def _has_slot_conflict(claims: list[dict[str, Any]]) -> bool:
    seen: dict[str, str] = {}
    for claim in claims:
        if _status(claim) != "active":
            continue
        slot = claim.get("slot")
        value = claim.get("value")
        if not slot or value in (None, ""):
            continue
        normalized = str(value).strip()
        if slot in seen and seen[slot] != normalized:
            return True
        seen[slot] = normalized
    return False


def _find_target(event: dict[str, Any], claim: dict[str, Any]) -> dict[str, Any] | None:
    target = _claim(event, claim.get("target_claim_id"))
    if target:
        return target
    slot = claim.get("slot")
    if slot:
        for item in event.get("claims", []):
            if item.get("slot") == slot and _status(item) == "active":
                return item
    if claim.get("claim_type") == "denial":
        for item in event.get("claims", []):
            if item.get("claim_type") == "rumor" and _status(item) != "denied":
                return item
    return None


def _summary(change_type: str, core_denial: bool, document: dict[str, Any]) -> str:
    if document.get("summary"):
        return document["summary"]
    if change_type == "correction":
        return "关键交易条款已更正；旧值保留在历史版本。"
    if change_type == "conflict":
        return "两份官方材料对关键交易数字给出不同值；存在未解冲突，不自动选边。"
    if change_type == "denial" and core_denial:
        return "核心收购命题被官方否认；原公告保留在历史版本。"
    if change_type == "denial":
        return "官方否认已入库；相关传闻 claim 标记为 denied。"
    if change_type == "rumor":
        return "出现新的传闻 claim，当前标记为未核实。"
    if change_type == "new_stage":
        return "同一 Storyline 出现新阶段；作为 linked Event 处理。"
    if change_type == "expiry":
        return "协议约定截止日已过且未见完成；标为过期/未完成。"
    return "事件出现新事实，已生成新版本。"


def _revision(
    event: dict[str, Any],
    document: dict[str, Any],
    now: str,
    change_type: str,
    core_denial: bool = False,
) -> dict[str, Any]:
    revisions = event.get("revisions") or []
    version = max([item.get("version", 0) for item in revisions] + [0]) + 1
    status_detail = event.get("status_detail") or derive_status(event["claims"])
    claim_ids = [
        claim["id"]
        for claim in event["claims"]
        if _status(claim) != "superseded"
    ]
    changed = {
        "update": ["claims_added", "summary"],
        "rumor": ["claims_added", "summary", "status_detail"],
        "denial": ["claims_added", "claims_denied", "summary", "status_detail"],
        "correction": ["claims_added", "claims_superseded", "summary", "status_detail"],
        "conflict": ["claims_added", "summary", "status_detail", "conflict"],
        "new_stage": ["linked_event"],
        "expiry": ["lifecycle_status", "summary"],
    }.get(change_type, ["claims_added", "summary"])
    strengths = [float(claim.get("strength", 0)) for claim in event["claims"] if _status(claim) != "superseded"]
    return {
        "id": f"rev_{version}",
        "event_id": event["id"],
        "version": version,
        "knowledge_at": now,
        "summary": _summary(change_type, core_denial, document),
        "status_detail": status_detail,
        "claim_ids": claim_ids,
        "changed_fields": changed,
        "reason": document.get("reason") or _summary(change_type, core_denial, document),
        "trigger_document_id": document["id"],
        "evidence_strength": max(strengths + [0]),
        "created_at": now,
    }


def _notification(
    change_type: str,
    event: dict[str, Any],
    revision: dict[str, Any],
    document: dict[str, Any],
    core_denial: bool = False,
) -> dict[str, Any] | None:
    if change_type == "rumor":
        level = "P2"
    elif change_type in {"denial", "correction", "conflict"}:
        level = "P0"
    else:
        level = "P1"

    if change_type == "denial":
        title = "核心收购被否认" if core_denial or event.get("core_status") == "denied" else "传闻被官方否认"
    elif change_type == "conflict":
        title = "官方来源存在冲突"
    elif change_type == "correction":
        title = "关键交易条款被更正"
    elif change_type == "new_stage":
        title = "交易进入新阶段"
    elif change_type == "expiry":
        title = "交易交割已过期"
    elif change_type == "rumor":
        title = "新增传闻，待核实"
    else:
        title = "事件出现新事实"

    return {
        "id": f"ntf_{document['id']}",
        "event_id": event["id"],
        "revision_id": revision["id"],
        "level": level,
        "title": title,
        "body": revision["summary"],
        "why": f"你关注了{(event.get('slots') or {}).get('actor', '该标的')}；规则={level} {change_type}。",
        "created_at": revision["knowledge_at"],
        "read_at": None,
        "diff_json": {
            "change_type": change_type,
            "version": revision["version"],
            "changed_fields": revision["changed_fields"],
        },
    }


def _linked_event(event: dict[str, Any], document: dict[str, Any], now: str) -> dict[str, Any]:
    claims = []
    for index, raw in enumerate(document.get("claims", []), start=1):
        claim = deepcopy(raw)
        claim.setdefault("id", f"clm_{document['id']}_{index}")
        claim["document_id"] = document["id"]
        claim["introduced_at"] = now
        claim["status"] = claim.get("status") or "active"
        claims.append(claim)
    linked = {
        "id": f"evt_{document['id']}",
        "storyline_id": event.get("storyline_id"),
        "title": document.get("title") or "同一 Storyline 新阶段",
        "slots": document.get("slots") or {},
        "claims": claims,
        "revisions": [],
        "linked_to": event["id"],
        "core_status": "confirmed",
        "narrative_status": "none",
        "impact_status": "unverified",
        "summary": document.get("summary") or "同一 Storyline 的下一阶段，作为 linked Event 处理。",
    }
    revision = _revision(linked, document, now, "new_stage")
    linked["revisions"].append(revision)
    linked["current_revision_id"] = revision["id"]
    return linked


def apply_document(
    event: dict[str, Any],
    document: dict[str, Any],
    now: str | None = None,
) -> dict[str, Any]:
    """Apply one new document to an event and return the next state."""
    current = deepcopy(event)
    now = now_utc(now)
    match = match_event(document, [current])
    change_type = document.get("change_type") or infer_change_type(document)
    if not document.get("claims"):
        return {"action": "duplicate", "event": current, "match": match, "revision": None, "notification": None}

    if match["decision"] == "new":
        linked = _linked_event(current, document, now)
        return {
            "action": "new_event",
            "event": current,
            "new_event": linked,
            "match": match,
            "revision": linked["revisions"][0],
            "notification": _notification("update", linked, linked["revisions"][0], document),
        }

    if match["decision"] == "review":
        return {"action": "review", "event": current, "match": match, "revision": None, "notification": None}

    if match["decision"] == "link":
        if change_type == "new_stage":
            linked = _linked_event(current, document, now)
            current.setdefault("linked_event_ids", []).append(linked["id"])
            return {
                "action": "linked_event",
                "event": current,
                "new_event": linked,
                "match": match,
                "revision": linked["revisions"][0],
                "notification": _notification("new_stage", current, linked["revisions"][0], document),
            }
        return {"action": "linked_related", "event": current, "match": match, "revision": None, "notification": None}

    current.setdefault("claims", [])
    current.setdefault("revisions", [])
    core_denial = False
    for index, raw in enumerate(document.get("claims", []), start=1):
        claim = deepcopy(raw)
        claim.setdefault("id", f"clm_{document['id']}_{index}")
        claim["document_id"] = document["id"]
        claim["introduced_at"] = now
        claim_type = claim.get("claim_type", "fact")

        if claim_type == "denial":
            target = _find_target(current, claim)
            if target:
                target["status"] = "denied"
                target["denied_by"] = claim["id"]
                if target.get("claim_role") == "acquisition_fact" and claim.get("core_denial"):
                    core_denial = True
            claim["status"] = "active"
        elif claim_type == "correction":
            target = _find_target(current, claim)
            if target:
                target["status"] = "superseded"
                target["superseded_by"] = claim["id"]
                claim["claim_role"] = target.get("claim_role", "acquisition_fact")
            claim["status"] = "active"
        elif claim_type == "rumor":
            claim["status"] = "unverified"
        else:
            claim["status"] = "active"
        current["claims"].append(claim)

    current["status_detail"] = derive_status(current["claims"])
    current["core_status"] = current["status_detail"]["core"]
    current["narrative_status"] = current["status_detail"]["narrative"]
    current["impact_status"] = current["status_detail"]["impact"]
    current["updated_at"] = now

    revision = _revision(current, document, now, change_type, core_denial=core_denial)
    current["revisions"].append(revision)
    current["current_revision_id"] = revision["id"]
    current["summary"] = revision["summary"]
    notification = _notification(change_type, current, revision, document, core_denial=core_denial)
    return {
        "action": "updated",
        "event": current,
        "match": match,
        "revision": revision,
        "notification": notification,
    }


def expire_event(
    event: dict[str, Any],
    deadline: str | None,
    now: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """Expire only when there is an explicit deadline and no completion claim."""
    if not deadline:
        return {"action": "noop", "reason": "没有明确截止日，不能标记过期。"}
    now = now_utc(now)
    def parsed(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed(now) < parsed(deadline):
        return {"action": "noop", "reason": "截止日尚未到达。"}
    if any(
        _status(claim) == "active"
        and any(word in claim.get("text", "") for word in ("交割完成", "完成交割", "已交割"))
        for claim in event.get("claims", [])
    ):
        return {"action": "noop", "reason": "已有完成交割的有效 claim。"}

    current = deepcopy(event)
    current["lifecycle_status"] = "expired"
    current["status_detail"] = {**derive_status(current.get("claims", [])), "lifecycle": "expired"}
    current["updated_at"] = now
    summary_text = summary or "协议约定截止日已过且未见完成；标为过期/未完成，不写成假。"
    revision = _revision(
        current,
        {"id": f"expiry_{event['id']}", "summary": summary_text},
        now,
        "expiry",
    )
    current.setdefault("revisions", []).append(revision)
    current["current_revision_id"] = revision["id"]
    current["summary"] = revision["summary"]
    notification = _notification(
        "expiry",
        current,
        revision,
        {"id": f"expiry_{event['id']}", "summary": summary_text},
    )
    return {"action": "expired", "event": current, "revision": revision, "notification": notification}
