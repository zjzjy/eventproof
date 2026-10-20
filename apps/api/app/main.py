from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .engine import apply_document, expire_event


ROOT = Path(__file__).resolve().parents[3]
WEB_DIST = ROOT / "apps" / "web" / "dist"
ENV_PATH = ROOT / ".env"
JSON_FIELDS = {
    "status_detail",
    "strength_json",
    "claim_ids",
    "changed_fields",
    "shared_slots",
    "differences",
    "diff_json",
    "snippets",
    "output_json",
}


def parse_json_fields(item: dict[str, Any]) -> dict[str, Any]:
    for field in JSON_FIELDS:
        value = item.get(field)
        if isinstance(value, str):
            try:
                item[field] = json.loads(value)
            except json.JSONDecodeError:
                pass
    return item


def normalize_as_of(value: str | None) -> str | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def env_value(key: str) -> str | None:
    value = os.getenv(key)
    if value:
        return value
    if not ENV_PATH.exists():
        return None
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            name, current = line.split("=", 1)
            if name.strip() == key:
                return current.strip()
    return None


def revisions_for(event_id: str) -> list[dict[str, Any]]:
    items = [parse_json_fields(row) for row in db.rows("revisions", "event_id = ?", (event_id,))]
    return sorted(items, key=lambda item: item["version"])


def revision_at(revisions: list[dict[str, Any]], as_of: str | None) -> dict[str, Any] | None:
    if not revisions:
        return None
    if not as_of:
        return revisions[-1]
    candidates = [item for item in revisions if item["knowledge_at"] <= as_of]
    return candidates[-1] if candidates else None


def status_at(claim: dict[str, Any], revision: dict[str, Any]) -> str:
    if claim.get("claim_role") == "rumor" and revision["version"] < 3:
        return "unverified"
    return claim.get("status", "active")


def claim_sort_key(claim: dict[str, Any]) -> tuple[int, float]:
    order = {"acquisition_fact": 0, "market_reaction": 1, "rumor": 2, "denial": 3}
    return order.get(claim.get("claim_role", ""), 9), -float(claim.get("strength", 0))


def event_payload(event_id: str, as_of_raw: str | None = None) -> dict[str, Any]:
    event = db.row("events", "id = ?", (event_id,))
    if not event:
        raise HTTPException(status_code=404, detail="event not found")
    event = parse_json_fields(event)
    try:
        as_of = normalize_as_of(as_of_raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="as_of must be an ISO-8601 timestamp") from exc
    revisions = revisions_for(event_id)
    revision = revision_at(revisions, as_of)
    if not revision:
        raise HTTPException(status_code=404, detail="no event version known at this time")

    all_claims = [parse_json_fields(row) for row in db.rows("claims", "event_id = ?", (event_id,))]
    visible_ids = set(revision.get("claim_ids") or [])
    claims = []
    for claim in all_claims:
        if claim["id"] not in visible_ids:
            continue
        claim["status"] = status_at(claim, revision)
        claim["is_inferred"] = bool(claim.get("is_inferred"))
        claims.append(claim)
    claims.sort(key=claim_sort_key)

    documents = [parse_json_fields(row) for row in db.rows("documents", "event_id = ?", (event_id,))]
    visible_docs = []
    for doc in documents:
        doc_claims = sorted(
            [claim for claim in claims if claim["document_id"] == doc["id"]],
            key=claim_sort_key,
        )
        if not doc_claims:
            continue
        doc["claims"] = doc_claims
        doc["claim_count"] = len(doc_claims)
        visible_docs.append(doc)
    visible_docs.sort(
        key=lambda item: (
            item.get("published_at") or "",
            item.get("sort_order") or 0,
            item.get("id") or "",
        )
    )

    merges = [
        parse_json_fields(row)
        for row in db.rows("merge_decisions", "event_id = ?", (event_id,))
    ]
    doc_titles = {doc["id"]: doc["title"] for doc in documents}
    for merge in merges:
        merge["document_title"] = doc_titles.get(merge["document_id"], merge["document_id"])
    merges.sort(key=lambda item: item.get("created_at", ""))

    current = {
        **event,
        "summary": revision["summary"],
        "verification_status": revision["verification_status"],
        "lifecycle_status": revision["lifecycle_status"],
        "impact_status": revision["impact_status"],
        "status_detail": revision["status_detail"],
        "evidence_strength": revision["evidence_strength"],
        "current_revision_id": revision["id"],
        "revision": revision,
        "revisions": revisions,
        "claims": claims,
        "documents": visible_docs,
        "merge_decisions": merges,
        "as_of": as_of,
        "is_replay": bool(as_of),
        "sources_count": len(visible_docs),
        "independent_sources_count": 1,
        "denied_claims_count": sum(1 for claim in claims if claim["status"] == "denied"),
        "active_claims_count": sum(1 for claim in claims if claim["status"] == "active"),
        "available_as_of": [
            {
                "version": item["version"],
                "label": ["08-05 公告", "08-07 传闻", "08-07 否认", "现在"][
                    min(item["version"] - 1, 3)
                ],
                "knowledge_at": item["knowledge_at"],
                "summary": item["summary"],
            }
            for item in revisions
        ],
    }
    return current


def revision_by_version(event_id: str, version: int) -> dict[str, Any] | None:
    found = db.row("revisions", "event_id = ? AND version = ?", (event_id, version))
    return parse_json_fields(found) if found else None


def claim_map(event_id: str) -> dict[str, dict[str, Any]]:
    return {
        claim["id"]: parse_json_fields(claim)
        for claim in db.rows("claims", "event_id = ?", (event_id,))
    }


def diff_payload(event_id: str, from_version: int, to_version: int) -> dict[str, Any]:
    left = revision_by_version(event_id, from_version)
    right = revision_by_version(event_id, to_version)
    if not left or not right:
        raise HTTPException(status_code=404, detail="revision not found")
    claims = claim_map(event_id)
    left_ids = set(left.get("claim_ids") or [])
    right_ids = set(right.get("claim_ids") or [])
    added = [claims[cid] for cid in sorted(right_ids - left_ids) if cid in claims]
    removed = [claims[cid] for cid in sorted(left_ids - right_ids) if cid in claims]
    status_changes = []
    for cid in sorted(left_ids & right_ids):
        claim = claims.get(cid)
        if not claim:
            continue
        before = status_at(claim, left)
        after = status_at(claim, right)
        if before != after:
            status_changes.append({"claim": claim, "from": before, "to": after})
    return {
        "from": left,
        "to": right,
        "added": added,
        "removed": removed,
        "status_changes": status_changes,
        "changed_fields": right.get("changed_fields") or [],
        "summary_from": left["summary"],
        "summary_to": right["summary"],
        "reason": right.get("reason"),
        "trigger_document_id": right.get("trigger_document_id"),
    }


def notification_payload(as_of_raw: str | None = None) -> dict[str, Any]:
    as_of = normalize_as_of(as_of_raw)
    items = [parse_json_fields(row) for row in db.rows("notifications")]
    if as_of:
        items = [item for item in items if item["created_at"] <= as_of]
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {"items": items, "unread": sum(1 for item in items if not item.get("read_at"))}


def meta_payload() -> dict[str, Any]:
    meta_row = db.row("app_meta", "key = ?", ("app_meta",))
    meta = json.loads(meta_row["value"]) if meta_row else {}
    meta["service"] = "EventProof"
    meta["version"] = "0.1.0"
    meta["data_mode"] = "fixture"
    return meta


def export_markdown(event_id: str, as_of_raw: str | None = None) -> str:
    event = event_payload(event_id, as_of_raw)
    meta = meta_payload()
    lines = [
        f"# {event['title']}",
        "",
        f"> {event['primary_entity']}（{event['security_code']}） · 事证 EventProof 证据包",
        f"> 导出时间：{datetime.now(timezone.utc).isoformat()}",
        f"> 数据截至：{event['as_of'] or event['data_as_of']}",
        "",
        "## 当前结论",
        "",
        event["summary"],
        "",
        f"- 核实状态：{event['verification_status']}",
        f"- 生命周期：{event['lifecycle_status']}",
        f"- 影响状态：{event['impact_status']}",
        f"- 证据强度：{event['evidence_strength']}/100",
        "",
        "## 时间",
        "",
        f"- 事情发生：{event['occurred_at']}（精度：{event['occurred_precision']}）",
        f"- 披露时间：{event['disclosed_at']}（精度：{event['disclosed_precision']}）",
        f"- 首次抓取：{event['first_ingested_at']}",
        f"- 最近更新：{event['updated_at']}",
        "",
        "## 事件串与证据",
        "",
    ]
    for index, doc in enumerate(event["documents"], start=1):
        lines.extend(
            [
                f"### #{index:02d} {doc['title']}",
                "",
                f"- 来源：{doc['source']}（{doc['source_tier']}）",
                f"- 披露：{doc['published_at']}",
                f"- 原文：{doc['url']}",
                "",
            ]
        )
        for claim in doc["claims"]:
            lines.extend(
                [
                    f"- **[{claim['claim_type']}] {claim['text']}**",
                    f"  - 状态：{claim['status']}；证据强度：{claim['strength']}（{claim['strength_band']}）",
                    f"  - 原文引用：\"{claim['quote']}\"",
                    f"  - 权重拆解：{json.dumps(claim['strength_json'], ensure_ascii=False)}",
                ]
            )
        lines.append("")
    lines.extend(["## 版本记录", "", "| 版本 | knowledge_at | 结论 | 变化 |", "| --- | --- | --- | --- |"])
    for revision in event["revisions"]:
        lines.append(
            f"| v{revision['version']} | {revision['knowledge_at']} | {revision['summary']} | "
            f"{', '.join(revision.get('changed_fields') or [])} |"
        )
    lines.extend(["", "## 合并依据", ""])
    for merge in event["merge_decisions"]:
        lines.append(
            f"- {merge['document_title']}：{merge['relation']}，score={merge['score']}，"
            f"{merge['reason']}"
        )
    lines.extend(
        [
            "",
            "## AI 使用与边界",
            "",
            f"- 模型：{meta.get('model')}；prompt：{meta.get('prompt_version')}；估算成本：¥{meta.get('total_cost_cny')}",
            f"- 说明：{meta.get('data_note')}",
            "- 本证据包只做事件事实整理与证据追溯，不构成投资建议。",
            "",
        ]
    )
    return "\n".join(lines)


SCENARIO_META: dict[str, dict[str, Any]] = {
    "correction": {
        "conclusion": "收购已确认，但对价由3亿元更正为2.8亿元；25%股权、分四期、不并表的安排不变；英伟达合作与2000亿市场传闻仍被否认。",
        "tags": [["收购已确认（对价已更正）", "green"], ["传闻已否认", "red"]],
        "mark_first": "已被更正",
        "date": "08-09",
        "time": "10:00 · v5",
        "label": "更正",
        "tone": "red",
        "tier": "A",
        "text": "更正公告：交易对价由3亿元更正为2.8亿元；25%股权、分四期、不并表的安排不变。",
        "quote": "“更正后交易对价为人民币2.8亿元” · 演示更正公告",
        "note": "旧值3亿元保留在 v1，不删除；这是对关键数字的更正，不是重写历史。",
        "why": "公司更正公告，直接修改关键交易数字；旧值仍可回放。",
        "change_line": "08-09 v5 对价更正",
        "last_update": "08-09 10:00",
        "last_version": "v5",
        "last_status": "对价更正",
    },
    "core-denial": {
        "conclusion": "公司否认收购佳贤通信25%股权；原公告保留在历史版本；英伟达合作与2000亿市场传闻仍被否认。",
        "tags": [["核心事实被否认", "red"], ["传闻已否认", "red"]],
        "mark_first": "核心已否认",
        "date": "08-09",
        "time": "10:00 · v5",
        "label": "否认",
        "tone": "red",
        "tier": "A",
        "text": "公司公告：不存在收购佳贤通信25%股权的交易安排。",
        "quote": "“公司不存在上述收购安排” · 演示否认公告",
        "note": "原收购公告保留在 v1；核心命题被否认，事件状态变为 denied。",
        "why": "官方否认核心命题，直接推翻原交易事实。",
        "change_line": "08-09 v5 核心收购被否认",
        "last_update": "08-09 10:00",
        "last_version": "v5",
        "last_status": "核心否认",
    },
    "conflict": {
        "conclusion": "两份官方材料对交易对价给出不同数值（3亿元 vs 2.8亿元）；存在未解冲突，系统不自动选边；英伟达合作与2000亿市场传闻仍被否认。",
        "tags": [["官方来源冲突", "amber"], ["传闻已否认", "red"]],
        "mark_first": "存在冲突",
        "date": "08-09",
        "time": "10:00 · v5",
        "label": "冲突",
        "tone": "amber",
        "tier": "A",
        "text": "另一份官方材料披露交易对价为2.8亿元，与08-05公告的3亿元不一致；未见更正公告。",
        "quote": "“另一份官方材料披露对价为2.8亿元” · 演示冲突材料",
        "note": "两个 A 级官方来源互相矛盾，系统保留两个值，不自动选边。",
        "why": "来源等级高不代表结论唯一；关键槽位冲突时标为 disputed。",
        "change_line": "08-09 v5 官方来源冲突",
        "last_update": "08-09 10:00",
        "last_version": "v5",
        "last_status": "存在冲突",
    },
    "expiry": {
        "conclusion": "收购已确认，但协议约定的交割截止日已过且未见完成；标为过期/未完成，不写成“假”；英伟达合作与2000亿市场传闻仍被否认。",
        "tags": [["收购已确认", "green"], ["交割已过期", "amber"], ["传闻已否认", "red"]],
        "mark_first": None,
        "date": "09-30",
        "time": "18:00 · v5",
        "label": "过期",
        "tone": "amber",
        "tier": "B",
        "text": "协议约定交割截止日已过，未见完成公告；标为过期/未完成。",
        "quote": "“协议约定交割截止日为2026-09-30” · 演示到期检查",
        "note": "过期只表示未按期完成，不表示交易是假；原始公告与否认记录保留。",
        "why": "依据明确截止日 + 无完成公告；不是仅因“很久没更新”。",
        "change_line": "09-30 v5 交割过期",
        "last_update": "09-30 18:00",
        "last_version": "v5",
        "last_status": "交割过期",
    },
    "new-stage": {
        "conclusion": "收购已确认并进入签署股份转让协议阶段；这是同一 Storyline 的新 Event，不合并原 Event；英伟达合作与2000亿市场传闻仍被否认。",
        "tags": [["收购已确认", "green"], ["新阶段", "blue"], ["传闻已否认", "red"]],
        "mark_first": None,
        "date": "09-22",
        "time": "18:00 · linked v1",
        "label": "新阶段",
        "tone": "blue",
        "tier": "A",
        "text": "公司签署股份转让协议；这是同一交易 Storyline 的下一阶段，不是原 Event 的新 claim。",
        "quote": "“关于对外投资购买股权暨签署股份转让协议的公告” · 演示公告",
        "note": "同一 Storyline 下新建 Event（follows），不把原收购 Event 合并/改写。",
        "why": "交易所公告，确认交易进入签约阶段。",
        "change_line": "09-22 linked Event v1 签署协议",
        "last_update": "09-22 18:00",
        "last_version": "linked v1",
        "last_status": "签署协议",
    },
}


def _engine_base(event: dict[str, Any]) -> dict[str, Any]:
    detail = event.get("status_detail") or {}
    return {
        "id": event["id"],
        "storyline_id": event.get("storyline_id"),
        "title": event.get("title"),
        "slots": {"actor": "通宇通讯", "target": "佳贤通信", "action": "acquisition"},
        "core_status": event.get("verification_status", "confirmed"),
        "narrative_status": detail.get("narrative", "none"),
        "impact_status": event.get("impact_status", "unverified"),
        "claims": event.get("claims", []),
        "revisions": event.get("revisions", []),
        "current_revision_id": event.get("current_revision_id"),
        "updated_at": event.get("updated_at"),
    }


def _scenario_document(event_id: str, scenario: str) -> dict[str, Any]:
    base = {
        "refs": [event_id],
        "slots": {"actor": "通宇通讯", "target": "佳贤通信", "action": "acquisition"},
    }
    if scenario == "correction":
        return {
            **base,
            "id": "scenario_correction",
            "title": "关于交易对价的更正公告（演示）",
            "published_at": "2026-08-09T10:00:00Z",
            "summary": SCENARIO_META[scenario]["conclusion"],
            "claims": [
                {
                    "id": "clm_scenario_correction_amount",
                    "claim_type": "correction",
                    "target_claim_id": "clm_ty_20260805_investment_1",
                    "slot": "amount",
                    "text": "交易对价由3亿元更正为2.8亿元",
                    "quote": "更正后交易对价为人民币2.8亿元",
                    "value": "2.8亿元",
                    "strength": 95,
                }
            ],
        }
    if scenario == "core-denial":
        return {
            **base,
            "id": "scenario_core_denial",
            "title": "关于收购事项的否认公告（演示）",
            "published_at": "2026-08-09T10:00:00Z",
            "summary": SCENARIO_META[scenario]["conclusion"],
            "claims": [
                {
                    "id": "clm_scenario_core_denial",
                    "claim_type": "denial",
                    "target_claim_id": "clm_ty_20260805_investment_1",
                    "core_denial": True,
                    "text": "公司不存在收购佳贤通信25%股权的交易安排",
                    "quote": "公司不存在上述收购安排",
                    "strength": 96,
                }
            ],
        }
    if scenario == "conflict":
        return {
            **base,
            "id": "scenario_conflict",
            "title": "另一份官方材料（演示）",
            "published_at": "2026-08-09T10:00:00Z",
            "conflict": True,
            "summary": SCENARIO_META[scenario]["conclusion"],
            "claims": [
                {
                    "id": "clm_scenario_conflict_amount",
                    "claim_type": "fact",
                    "claim_role": "acquisition_fact",
                    "slot": "amount",
                    "value": "2.8亿元",
                    "conflict": True,
                    "text": "另一份官方材料披露交易对价为2.8亿元",
                    "quote": "另一份官方材料披露对价为2.8亿元",
                    "strength": 94,
                }
            ],
        }
    if scenario == "new-stage":
        return {
            **base,
            "id": "scenario_new_stage",
            "title": "关于对外投资购买股权暨签署股份转让协议的公告（演示）",
            "published_at": "2026-09-22T18:00:00Z",
            "stage": "sign",
            "summary": SCENARIO_META[scenario]["conclusion"],
            "claims": [
                {
                    "id": "clm_scenario_signing",
                    "claim_type": "fact",
                    "claim_role": "acquisition_fact",
                    "text": "公司签署股份转让协议",
                    "quote": "关于对外投资购买股权暨签署股份转让协议的公告",
                    "strength": 95,
                }
            ],
        }
    raise HTTPException(status_code=404, detail="scenario not found")


def scenario_result(event_id: str, scenario: str) -> dict[str, Any]:
    if scenario not in SCENARIO_META:
        raise HTTPException(status_code=404, detail="scenario not found")
    base = event_payload(event_id)
    engine_event = _engine_base(base)
    meta = SCENARIO_META[scenario]

    if scenario == "expiry":
        result = expire_event(
            engine_event,
            "2026-09-30T00:00:00Z",
            "2026-10-20T00:00:00Z",
            summary=meta["conclusion"],
        )
    else:
        document = _scenario_document(event_id, scenario)
        result = apply_document(engine_event, document, "2026-08-09T10:00:00Z")

    return {
        "scenario": scenario,
        "action": result.get("action"),
        "event": result.get("event"),
        "linked_event": result.get("new_event"),
        "revision": result.get("revision"),
        "notification": result.get("notification"),
        "change": meta,
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="EventProof", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "EventProof",
        "version": "0.1.0",
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@app.get("/health")
def health_alias() -> dict[str, Any]:
    return health()


@app.get("/api/health/db")
def health_db() -> dict[str, Any]:
    conn = db.connect()
    try:
        conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "database": "sqlite"}
    finally:
        conn.close()


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    return meta_payload()


@app.get("/api/events")
def list_events() -> dict[str, Any]:
    events = [parse_json_fields(row) for row in db.rows("events")]
    items = []
    for event in events:
        revisions = revisions_for(event["id"])
        revision = revisions[-1] if revisions else None
        claims = [parse_json_fields(row) for row in db.rows("claims", "event_id = ?", (event["id"],))]
        items.append(
            {
                "id": event["id"],
                "title": event["title"],
                "primary_entity": event["primary_entity"],
                "security_code": event["security_code"],
                "event_type": event["event_type"],
                "summary": revision["summary"] if revision else event["summary"],
                "verification_status": revision["verification_status"] if revision else event["verification_status"],
                "lifecycle_status": revision["lifecycle_status"] if revision else event["lifecycle_status"],
                "impact_status": revision["impact_status"] if revision else event["impact_status"],
                "status_detail": revision["status_detail"] if revision else event["status_detail"],
                "evidence_strength": revision["evidence_strength"] if revision else event["evidence_strength"],
                "updated_at": event["updated_at"],
                "sources_count": len(db.rows("documents", "event_id = ?", (event["id"],))),
                "denied_claims_count": sum(1 for claim in claims if claim["status"] == "denied"),
                "revision_count": len(revisions),
            }
        )
    return {"items": items}


@app.get("/api/events/{event_id}")
def get_event(event_id: str, as_of: str | None = Query(default=None)) -> dict[str, Any]:
    return event_payload(event_id, as_of)


@app.get("/api/events/{event_id}/revisions")
def get_revisions(event_id: str) -> dict[str, Any]:
    return {"items": revisions_for(event_id)}


@app.get("/api/events/{event_id}/diff")
def get_diff(
    event_id: str,
    from_version: int = Query(default=1, ge=1),
    to_version: int = Query(default=2, ge=1),
) -> dict[str, Any]:
    return diff_payload(event_id, from_version, to_version)


@app.get("/api/events/{event_id}/merge")
def get_merge(event_id: str) -> dict[str, Any]:
    merges = [parse_json_fields(row) for row in db.rows("merge_decisions", "event_id = ?", (event_id,))]
    docs = {row["id"]: row["title"] for row in db.rows("documents", "event_id = ?", (event_id,))}
    for merge in merges:
        merge["document_title"] = docs.get(merge["document_id"], merge["document_id"])
    return {"items": merges}


@app.get("/api/claims/{claim_id}")
def get_claim(claim_id: str) -> dict[str, Any]:
    claim = db.row("claims", "id = ?", (claim_id,))
    if not claim:
        raise HTTPException(status_code=404, detail="claim not found")
    claim = parse_json_fields(claim)
    doc = db.row("documents", "id = ?", (claim["document_id"],))
    claim["document"] = parse_json_fields(doc) if doc else None
    return claim


@app.get("/api/notifications")
def get_notifications(as_of: str | None = Query(default=None)) -> dict[str, Any]:
    return notification_payload(as_of)


@app.post("/api/notifications/{notification_id}/read")
def read_notification(notification_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ok = db.mark_notification_read(notification_id, now)
    if not ok:
        raise HTTPException(status_code=404, detail="notification not found")
    return {"ok": True, "read_at": now}


@app.post("/api/demo/reset")
def reset_demo(x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    expected = env_value("ADMIN_TOKEN")
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=401, detail="admin token required")
    db.reset_db()
    return {"ok": True, "message": "demo data reset"}


@app.get("/api/events/{event_id}/export")
def export_event(event_id: str, as_of: str | None = Query(default=None)) -> Response:
    markdown = export_markdown(event_id, as_of)
    return PlainTextResponse(
        markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="eventproof-{event_id}.md"',
        },
    )


@app.get("/api/events/{event_id}/scenario/{scenario}")
def get_scenario(event_id: str, scenario: str) -> dict[str, Any]:
    return scenario_result(event_id, scenario)


@app.post("/api/engine/apply")
def engine_apply(payload: dict[str, Any]) -> dict[str, Any]:
    event = payload.get("event")
    document = payload.get("document")
    if not isinstance(event, dict) or not isinstance(document, dict):
        raise HTTPException(status_code=422, detail="event and document are required objects")
    return apply_document(event, document, payload.get("now"))


@app.post("/api/engine/expire")
def engine_expire(payload: dict[str, Any]) -> dict[str, Any]:
    event = payload.get("event")
    if not isinstance(event, dict):
        raise HTTPException(status_code=422, detail="event is required")
    return expire_event(event, payload.get("deadline"), payload.get("now"))


if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
else:
    @app.get("/")
    def index() -> dict[str, str]:
        return {
            "app": "EventProof",
            "message": "Frontend not built yet. Run npm install && npm run build in apps/web.",
            "api": "/api/events",
            "docs": "/docs",
        }
