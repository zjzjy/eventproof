"""Precompute the hero event from the four official source documents.

The script uses Alibaba Cloud Bailian (OpenAI-compatible) once per document,
validates every quote against the source snippets, scores evidence with a
deterministic formula, and writes fixtures/tongyu/precomputed.json.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.resilience import call_with_retry, extract_json_object, validate_source_text  # noqa: E402

SOURCES = ROOT / "fixtures" / "tongyu" / "sources.json"
OUTPUT = ROOT / "fixtures" / "tongyu" / "precomputed.json"
PROMPT_VERSION = "claim_extract_v1"
MODEL = os.getenv("LLM_MODEL_FAST", "qwen3.8-flash")

EVENT_ID = "evt_tongyu_20260805"
STORYLINE_ID = "story_tongyu_jia_xian"

TYPE_MAP = {
    "事实": "fact",
    "观点": "opinion",
    "推测": "speculation",
    "传闻": "rumor",
    "否认": "denial",
    "更正": "correction",
}
ALLOWED_TYPES = {"fact", "opinion", "speculation", "rumor", "denial", "correction"}


def load_env() -> dict[str, str]:
    env = {}
    path = ROOT / ".env"
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def iso_utc(value: str) -> str:
    return (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def call_llm(env: dict[str, str], doc: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_source_text(doc["id"], "\n".join(s["text"] for s in doc["snippets"]))
    snippets = "\n".join(f"[{i + 1}] {s['text']}" for i, s in enumerate(doc["snippets"]))
    system = """你是投资事件 claim 抽取器。只输出合法 JSON，不要 markdown。
把给定公告片段拆成原子主张。每条主张必须能在原文中找到连续 quote。

claim_type 只能是：
- fact：可核验的陈述
- opinion：评价、判断、立场
- speculation：对未来的推测（预计/有望/或将）
- rumor：未经证实的流传说法（据传/网传/市场消息/媒体报道）
- denial：对既有说法的否定
- correction：对既有说法的更正

规则：
1. quote 必须是原文连续子串，不改写。
2. 金额、比例、日期、条件分别拆成 claim，不要合并。
3. 公司转述网络传闻时，传闻本身是 rumor；公司自己的否定是 denial。
4. 否定句的 text 描述被否认的内容，quote 用否定句原文。
5. 不确定的时间留空，不要编造。
6. 每条 claim 必须有 quote；没有 quote 的不要输出。

输出 JSON：
{"claims":[{"text":"","claim_type":"","subject":"","predicate":"","object":"","value":null,"unit":"","quote":"","hedge":"none","confidence":0.0}]}
"""
    user = (
        f"文档标题：{doc['title']}\n"
        f"披露日期：{doc['published_at'][:10]}\n"
        f"来源：{doc['source']} / {doc['doc_type']}\n"
        f"片段：\n{snippets}"
    )
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "max_tokens": 1600,
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
    }
    response = call_with_retry(
        lambda: requests.post(
            env["LLM_BASE_URL"].rstrip("/") + "/chat/completions",
            headers={
                "Authorization": "Bearer " + env["LLM_API_KEY"],
                "Content-Type": "application/json",
            },
            json=body,
            timeout=120,
        )
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    parsed = extract_json_object(content)
    items = parsed.get("claims") if isinstance(parsed, dict) else parsed
    if not isinstance(items, list):
        items = []
    usage = payload.get("usage", {})
    record = {
        "task": "claim_extract",
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "input_hash": hashlib.sha256((system + user).encode("utf-8")).hexdigest()[:16],
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "valid": True,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    record["cost_cny"] = round(
        record["prompt_tokens"] * 0.000001 + record["completion_tokens"] * 0.000002, 6
    )
    return items, record


def validate_claims(raw_claims: list[dict[str, Any]], doc: dict[str, Any]) -> list[dict[str, Any]]:
    source = compact(" ".join(s["text"] for s in doc["snippets"]))
    valid = []
    for raw in raw_claims:
        if not isinstance(raw, dict):
            continue
        claim_type = str(raw.get("claim_type", "")).strip()
        claim_type = TYPE_MAP.get(claim_type, claim_type)
        if claim_type not in ALLOWED_TYPES:
            continue
        quote = str(raw.get("quote", "")).strip()
        if len(quote) < 4 or compact(quote) not in source:
            continue
        text = str(raw.get("text", "")).strip()
        if len(text) < 4:
            text = quote
        try:
            confidence = float(raw.get("confidence", 0.8))
        except (TypeError, ValueError):
            confidence = 0.8
        confidence = max(0.0, min(1.0, confidence))
        valid.append(
            {
                "text": text,
                "claim_type": claim_type,
                "subject": str(raw.get("subject", "")).strip(),
                "predicate": str(raw.get("predicate", "")).strip(),
                "object": str(raw.get("object", "")).strip(),
                "value": raw.get("value"),
                "unit": str(raw.get("unit", "")).strip(),
                "quote": quote,
                "hedge": str(raw.get("hedge", "none")).strip() or "none",
                "confidence": confidence,
            }
        )
    return valid


def score_claim(claim: dict[str, Any], role: str) -> tuple[float, dict[str, float], str, str]:
    if role == "rumor":
        factors = {
            "authority": 0.20,
            "directness": 0.50,
            "independence": 0.30,
            "specificity": 1.00,
            "corroboration": 0.20,
            "extraction": claim["confidence"],
        }
        cap = 35.0
        explanation = "传闻来自网络媒体转述，未获得原始报道；按规则上限 35 分，转载不增加独立性。"
    elif role == "denial":
        factors = {
            "authority": 0.95,
            "directness": 1.00,
            "independence": 1.00,
            "specificity": 0.90,
            "corroboration": 0.40,
            "extraction": claim["confidence"],
        }
        cap = None
        explanation = "公司官方澄清，直接否定具体合作/协议；否认不随时间衰减。"
    elif role == "market_reaction":
        factors = {
            "authority": 0.95,
            "directness": 1.00,
            "independence": 1.00,
            "specificity": 1.00,
            "corroboration": 0.40,
            "extraction": claim["confidence"],
        }
        cap = None
        explanation = "交易所披露的股价异动事实；只能说明市场反应，不证明因果。"
    else:
        factors = {
            "authority": 0.95,
            "directness": 1.00,
            "independence": 1.00,
            "specificity": 1.00,
            "corroboration": 0.70,
            "extraction": claim["confidence"],
        }
        cap = None
        explanation = "公司公告直接披露交易条款，并被后续澄清公告再次引用。"

    score = 100 * (
        0.30 * factors["authority"]
        + 0.20 * factors["directness"]
        + 0.15 * factors["independence"]
        + 0.10 * factors["specificity"]
        + 0.15 * factors["corroboration"]
        + 0.10 * factors["extraction"]
    )
    if cap is not None:
        score = min(score, cap)
    score = round(score, 1)
    band = "strong" if score >= 75 else "medium" if score >= 45 else "weak"
    return score, factors, band, explanation


def assign_role(doc_id: str, claim_type: str) -> str:
    if claim_type == "rumor":
        return "rumor"
    if claim_type == "denial":
        return "denial"
    if doc_id.endswith("abnormal"):
        return "market_reaction"
    return "acquisition_fact"


def introduced_at(doc_id: str, claim_type: str) -> str:
    if doc_id == "ty_20260805_investment" or doc_id == "ty_20260805_abnormal":
        return "2026-08-05T10:00:00Z"
    if doc_id == "ty_20260807_clarification":
        return "2026-08-07T09:55:00Z" if claim_type == "rumor" else "2026-08-07T10:00:00Z"
    if doc_id == "ty_20260808_abnormal":
        return "2026-08-08T10:00:00Z"
    return "2026-08-05T10:00:00Z"


def keep_claim(claim: dict[str, Any]) -> bool:
    """Keep the demo event readable: retain key slots, drop repeated rumor copies."""
    doc_id = claim["document_id"]
    text = claim["text"] + " " + claim["quote"]
    if doc_id == "ty_20260808_abnormal" and claim["claim_type"] == "rumor":
        return False
    if (
        doc_id == "ty_20260807_clarification"
        and claim["claim_type"] == "rumor"
        and ("25%" in text or "25.00%" in text)
    ):
        # The 25% stake is confirmed by the official announcement; it is not a false rumor.
        return False
    if doc_id == "ty_20260805_investment":
        return any(
            key in text
            for key in ("30,000.00", "25.00%", "18,152,657", "10,891,594", "15%", "分四期", "不纳入")
        )
    if doc_id in {"ty_20260805_abnormal", "ty_20260808_abnormal"}:
        return "20%" in text or "涨幅偏离值" in text
    return True


def build() -> dict[str, Any]:
    env = load_env()
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    documents = sources["documents"]
    all_claims: list[dict[str, Any]] = []
    llm_calls: list[dict[str, Any]] = []

    for doc in documents:
        raw_claims, call = call_llm(env, doc)
        valid = validate_claims(raw_claims, doc)
        call["output_json"] = valid
        call["document_id"] = doc["id"]
        call["valid"] = len(valid) > 0
        llm_calls.append(call)
        if not valid:
            raise RuntimeError(f"No valid claims extracted for {doc['id']}")
        for index, claim in enumerate(valid, start=1):
            role = assign_role(doc["id"], claim["claim_type"])
            score, factors, band, explanation = score_claim(claim, role)
            all_claims.append(
                {
                    "id": f"clm_{doc['id']}_{index}",
                    "event_id": EVENT_ID,
                    "document_id": doc["id"],
                    **claim,
                    "claim_role": role,
                    "status": "denied" if role == "rumor" else "active",
                    "strength": score,
                    "strength_band": band,
                    "strength_json": factors,
                    "strength_explanation": explanation,
                    "introduced_at": introduced_at(doc["id"], claim["claim_type"]),
                    "is_inferred": True,
                    "source_tier": doc["source_tier"],
                }
            )

    # Deduplicate repeated rumor text from the second abnormal notice.
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for claim in all_claims:
        key = (claim["claim_type"], compact(claim["text"])[:60])
        if claim["claim_type"] == "rumor" and any(
            existing["claim_type"] == "rumor"
            and (compact(existing["text"])[:60] == key[1] or key[1] in compact(existing["text"]))
            for existing in deduped
        ):
            continue
        if key in seen:
            continue
        seen.add(key)
        deduped.append(claim)
    all_claims = deduped
    all_claims = [claim for claim in all_claims if keep_claim(claim)]

    by_doc: dict[str, list[dict[str, Any]]] = {}
    for claim in all_claims:
        by_doc.setdefault(claim["document_id"], []).append(claim)

    def ids(doc_ids: list[str], types: set[str] | None = None) -> list[str]:
        result = []
        for doc_id in doc_ids:
            for claim in by_doc.get(doc_id, []):
                if types is None or claim["claim_type"] in types:
                    result.append(claim["id"])
        return result

    v1_claims = ids(["ty_20260805_investment", "ty_20260805_abnormal"])
    rumor_claims = ids(["ty_20260807_clarification"], {"rumor"})
    denial_claims = [
        c["id"]
        for c in by_doc.get("ty_20260807_clarification", [])
        if c["claim_type"] in {"denial", "fact"}
    ]
    market_claims = ids(["ty_20260808_abnormal"], {"fact"})

    final_summary = (
        "公司公告拟以3亿元受让佳贤通信25%股权，分四期交割且不并表；"
        "公司随后否认佳贤与英伟达合作开发6G AI-RAN、瞄准2000亿元市场的传闻；"
        "传闻中25%入股比例与公告一致。"
    )
    v1_summary = "公司公告拟以3亿元受让佳贤通信25%股权，分四期交割且不并表。"
    v2_summary = "澄清公告提到“佳贤与英伟达合作开发6G AI-RAN、瞄准2000亿元市场”的传闻，等待核对。"
    v3_summary = final_summary
    v4_summary = (
        final_summary + " 公告披露2026年8月5日至7日三个交易日收盘涨幅偏离值累计超过20%。"
    )

    revisions = [
        {
            "id": "rev_1",
            "event_id": EVENT_ID,
            "version": 1,
            "knowledge_at": "2026-08-05T10:00:00Z",
            "summary": v1_summary,
            "verification_status": "confirmed",
            "lifecycle_status": "active",
            "impact_status": "unverified",
            "evidence_strength": 93.0,
            "status_detail": {"core": "confirmed", "narrative": "none", "market": "unverified"},
            "claim_ids": v1_claims,
            "changed_fields": ["initial"],
            "reason": "2026-08-05 对外投资公告与股价异动公告入库。",
            "trigger_document_id": "ty_20260805_investment",
            "is_inferred": True,
            "created_at": "2026-08-05T10:00:00Z",
        },
        {
            "id": "rev_2",
            "event_id": EVENT_ID,
            "version": 2,
            "knowledge_at": "2026-08-07T09:55:00Z",
            "summary": v2_summary,
            "verification_status": "confirmed",
            "lifecycle_status": "active",
            "impact_status": "unverified",
            "evidence_strength": 93.0,
            "status_detail": {"core": "confirmed", "narrative": "unverified", "market": "unverified"},
            "claim_ids": v1_claims + rumor_claims,
            "changed_fields": ["claims_added", "summary", "status_detail"],
            "reason": "澄清公告到达；先识别出被转述的英伟达合作传闻，尚未读到否认段。",
            "trigger_document_id": "ty_20260807_clarification",
            "is_inferred": True,
            "created_at": "2026-08-07T09:55:00Z",
        },
        {
            "id": "rev_3",
            "event_id": EVENT_ID,
            "version": 3,
            "knowledge_at": "2026-08-07T10:00:00Z",
            "summary": v3_summary,
            "verification_status": "confirmed",
            "lifecycle_status": "active",
            "impact_status": "unverified",
            "evidence_strength": 93.0,
            "status_detail": {"core": "confirmed", "narrative": "denied", "market": "unverified"},
            "claim_ids": v1_claims + rumor_claims + denial_claims,
            "changed_fields": [
                "claims_added",
                "claims_denied",
                "summary",
                "status_detail",
                "resolved_conflicts",
            ],
            "reason": "同一份澄清公告的否认段入库；传闻 claim 标记为 denied。",
            "trigger_document_id": "ty_20260807_clarification",
            "is_inferred": True,
            "created_at": "2026-08-07T10:00:00Z",
        },
        {
            "id": "rev_4",
            "event_id": EVENT_ID,
            "version": 4,
            "knowledge_at": "2026-08-08T10:00:00Z",
            "summary": v4_summary,
            "verification_status": "confirmed",
            "lifecycle_status": "active",
            "impact_status": "observed",
            "evidence_strength": 93.0,
            "status_detail": {"core": "confirmed", "narrative": "denied", "market": "observed"},
            "claim_ids": v1_claims + rumor_claims + denial_claims + market_claims,
            "changed_fields": ["claims_added", "summary", "impact_status"],
            "reason": "2026-08-08 股价异常波动公告入库，市场反应状态变为 observed。",
            "trigger_document_id": "ty_20260808_abnormal",
            "is_inferred": True,
            "created_at": "2026-08-08T10:00:00Z",
        },
    ]

    merge_decisions = [
        {
            "id": "merge_1",
            "event_id": EVENT_ID,
            "document_id": "ty_20260805_abnormal",
            "relation": "update",
            "score": 0.90,
            "decision": "auto_merge",
            "shared_slots": {"actor": "通宇通讯", "event_type": "股价异常波动"},
            "differences": ["不涉及交易条款", "补充市场反应"],
            "reason": "同一标的、同一公告窗口，作为收购事件的市场反应挂接。",
            "model": "rule_slot_match",
            "created_at": "2026-08-05T10:00:00Z",
        },
        {
            "id": "merge_2",
            "event_id": EVENT_ID,
            "document_id": "ty_20260807_clarification",
            "relation": "update",
            "score": 0.96,
            "decision": "auto_merge",
            "shared_slots": {
                "actor": "通宇通讯",
                "target": "佳贤通信",
                "stake": "25%",
                "amount": "3亿元",
            },
            "differences": ["新增英伟达合作传闻与官方否认"],
            "reason": "澄清公告显式引用2026-08-05对外投资公告，主体/标的/比例一致。",
            "model": "rule_slot_match",
            "created_at": "2026-08-07T10:00:00Z",
        },
        {
            "id": "merge_3",
            "event_id": EVENT_ID,
            "document_id": "ty_20260808_abnormal",
            "relation": "update",
            "score": 0.91,
            "decision": "auto_merge",
            "shared_slots": {"actor": "通宇通讯", "rumor": "英伟达6G AI-RAN", "window": "8月5-7日"},
            "differences": ["重复引用同一传闻，未新增独立来源", "新增市场异动窗口"],
            "reason": "后续异常波动公告再次引用同一传闻，挂接为市场反应，不重复计算来源。",
            "model": "rule_slot_match",
            "created_at": "2026-08-08T10:00:00Z",
        },
    ]

    notifications = [
        {
            "id": "ntf_1",
            "event_id": EVENT_ID,
            "revision_id": "rev_1",
            "level": "P1",
            "title": "通宇通讯公告拟以3亿元收购佳贤通信25%股权",
            "body": "公告披露交易金额3亿元、受让约25%股权，分四期交割，不纳入合并报表。",
            "why": "你关注了002792；规则=重大交易公告即时通知。",
            "created_at": "2026-08-05T10:05:00Z",
            "read_at": None,
            "diff_json": {"type": "initial", "status": "confirmed"},
        },
        {
            "id": "ntf_2",
            "event_id": EVENT_ID,
            "revision_id": "rev_3",
            "level": "P0",
            "title": "英伟达合作与2000亿市场传闻被公司否认",
            "body": "公司澄清：佳贤通信与英伟达不存在研发合作关系，未签署意向采购或供货协议；相关产品仍处前期研发阶段。",
            "why": "你关注了002792；规则=官方否认/澄清即时通知。",
            "created_at": "2026-08-07T10:05:00Z",
            "read_at": None,
            "diff_json": {
                "type": "denial",
                "narrative_status": {"from": "unverified", "to": "denied"},
                "added_claim_types": ["denial", "fact"],
            },
        },
        {
            "id": "ntf_3",
            "event_id": EVENT_ID,
            "revision_id": "rev_4",
            "level": "P1",
            "title": "澄清后股价仍三日涨幅偏离值超20%",
            "body": "2026年8月5日至7日三个交易日收盘价格涨幅偏离值累计超过20%。",
            "why": "你关注了002792；规则=关注标的的市场异动。",
            "created_at": "2026-08-08T10:05:00Z",
            "read_at": None,
            "diff_json": {"type": "market_reaction", "impact_status": {"from": "unverified", "to": "observed"}},
        },
    ]

    latest = revisions[-1]
    event = {
        "id": EVENT_ID,
        "storyline_id": STORYLINE_ID,
        "title": "通宇通讯收购佳贤通信25%股权",
        "event_type": "M&A",
        "primary_entity": "通宇通讯",
        "security_code": "002792",
        "exchange": "SZSE",
        "occurred_at": "2026-08-04",
        "occurred_precision": "day",
        "disclosed_at": "2026-08-05T00:00:00+08:00",
        "disclosed_precision": "day",
        "first_ingested_at": "2026-08-05T10:00:00Z",
        "updated_at": "2026-08-08T10:00:00Z",
        "verification_status": latest["verification_status"],
        "lifecycle_status": latest["lifecycle_status"],
        "impact_status": latest["impact_status"],
        "status_detail": latest["status_detail"],
        "evidence_strength": latest["evidence_strength"],
        "summary": latest["summary"],
        "current_revision_id": latest["id"],
        "data_as_of": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    documents_out = []
    for doc in documents:
        documents_out.append(
            {
                **doc,
                "event_id": EVENT_ID,
                "ingested_at": introduced_at(doc["id"], "fact"),
                "data_origin": "fixture",
                "claim_count": len(by_doc.get(doc["id"], [])),
            }
        )

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ai_mode": "precomputed",
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "total_cost_cny": round(sum(c["cost_cny"] for c in llm_calls), 6),
        "data_note": "Evidence quotes come from iFinD notice snippets; PDF URLs point to CNINFO originals. Time-of-day is inferred for demo as-of replay and marked is_inferred.",
        "curation": "Raw LLM claims are kept in llm_calls; the demo event keeps key slots and drops repeated rumor copies from the second abnormal notice.",
    }

    return {
        "meta": meta,
        "storyline": {
            "id": STORYLINE_ID,
            "title": "通宇通讯收购佳贤通信25%股权",
            "primary_entity": "通宇通讯",
        },
        "event": event,
        "documents": documents_out,
        "claims": all_claims,
        "revisions": revisions,
        "merge_decisions": merge_decisions,
        "notifications": notifications,
        "llm_calls": llm_calls,
    }


if __name__ == "__main__":
    result = build()
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUTPUT}")
    print(
        "claims=", len(result["claims"]),
        "revisions=", len(result["revisions"]),
        "cost_cny=", result["meta"]["total_cost_cny"],
    )
