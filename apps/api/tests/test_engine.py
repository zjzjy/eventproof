from copy import deepcopy

from app.engine import apply_document, expire_event, infer_change_type, match_event


def base_event():
    return {
        "id": "evt_1",
        "storyline_id": "story_1",
        "title": "A收购B",
        "slots": {"actor": "A", "target": "B", "action": "acquisition"},
        "core_status": "confirmed",
        "narrative_status": "unverified",
        "impact_status": "unverified",
        "claims": [
            {
                "id": "c_fact",
                "claim_type": "fact",
                "claim_role": "acquisition_fact",
                "status": "active",
                "text": "拟以3亿元收购B 25%股权",
                "quote": "拟以3亿元收购B 25%股权",
                "slot": "amount",
                "value": "3亿元",
                "strength": 94,
            },
            {
                "id": "c_stake",
                "claim_type": "fact",
                "claim_role": "acquisition_fact",
                "status": "active",
                "text": "受让25%股权",
                "quote": "受让25%股权",
                "slot": "stake",
                "strength": 94,
            },
            {
                "id": "c_rumor",
                "claim_type": "rumor",
                "claim_role": "rumor",
                "status": "unverified",
                "text": "与C合作开发6G",
                "quote": "与C合作开发6G",
                "strength": 35,
            },
        ],
        "revisions": [
            {
                "id": "rev_1",
                "version": 1,
                "knowledge_at": "2026-08-05T10:00:00Z",
                "summary": "初始公告",
                "changed_fields": ["initial"],
            }
        ],
        "current_revision_id": "rev_1",
        "updated_at": "2026-08-05T10:00:00Z",
    }


def doc(**overrides):
    value = {
        "id": "doc_2",
        "title": "后续公告",
        "refs": ["evt_1"],
        "slots": {"actor": "A", "target": "B", "action": "acquisition"},
        "claims": [],
    }
    value.update(overrides)
    return value


def test_explicit_reference_merges():
    match = match_event(doc(claims=[{"id": "x", "claim_type": "fact"}]), [base_event()])
    assert match["decision"] == "merge"
    assert match["score"] >= 0.9


def test_same_actor_different_target_links_not_merges():
    document = doc(refs=[], slots={"actor": "A", "target": "D", "action": "acquisition"}, claims=[{"id": "x", "claim_type": "fact"}])
    match = match_event(document, [base_event()])
    assert match["decision"] == "link"
    assert match["relation"] == "related"


def test_new_stage_links_follow_up():
    document = doc(stage="sign", claims=[{"id": "c_sign", "claim_type": "fact", "claim_role": "acquisition_fact", "text": "签署协议", "quote": "签署协议"}])
    match = match_event(document, [base_event()])
    assert match["decision"] == "link"
    assert match["relation"] == "follow_up"
    result = apply_document(base_event(), document, "2026-09-22T10:00:00Z")
    assert result["action"] == "linked_event"
    assert result["new_event"]["linked_to"] == "evt_1"
    assert len(result["event"]["claims"]) == 3
    assert result["notification"]["level"] == "P1"


def test_sub_claim_denial_keeps_core_confirmed():
    document = doc(
        claims=[
            {
                "id": "c_deny_rumor",
                "claim_type": "denial",
                "target_claim_id": "c_rumor",
                "text": "不存在合作",
                "quote": "不存在合作",
            }
        ]
    )
    result = apply_document(base_event(), document, "2026-08-07T10:00:00Z")
    event = result["event"]
    assert event["core_status"] == "confirmed"
    assert event["narrative_status"] == "denied"
    assert next(c for c in event["claims"] if c["id"] == "c_rumor")["status"] == "denied"
    assert result["notification"]["level"] == "P0"
    assert result["notification"]["title"] == "传闻被官方否认"
    assert result["revision"]["version"] == 2


def test_core_denial_changes_core_status():
    document = doc(
        claims=[
            {
                "id": "c_deny_core",
                "claim_type": "denial",
                "target_claim_id": "c_fact",
                "core_denial": True,
                "text": "不存在收购安排",
                "quote": "不存在收购安排",
            }
        ]
    )
    result = apply_document(base_event(), document, "2026-08-07T10:00:00Z")
    assert result["event"]["core_status"] == "denied"
    assert result["notification"]["title"] == "核心收购被否认"
    assert result["notification"]["level"] == "P0"


def test_conflicting_official_amount_marks_disputed():
    document = doc(
        conflict=True,
        claims=[
            {
                "id": "c_conflict",
                "claim_type": "fact",
                "claim_role": "acquisition_fact",
                "slot": "amount",
                "value": "2.8亿元",
                "conflict": True,
                "text": "另一份官方材料披露对价为2.8亿元",
                "quote": "另一份官方材料披露对价为2.8亿元",
            }
        ],
    )
    result = apply_document(base_event(), document, "2026-08-09T10:00:00Z")
    assert result["event"]["core_status"] == "disputed"
    assert result["notification"]["title"] == "官方来源存在冲突"
    assert result["notification"]["level"] == "P0"


def test_correction_supersedes_old_value():
    document = doc(
        claims=[
            {
                "id": "c_correct",
                "claim_type": "correction",
                "target_claim_id": "c_fact",
                "slot": "amount",
                "text": "更正为2.8亿元",
                "quote": "更正为2.8亿元",
                "value": "2.8亿元",
            }
        ]
    )
    result = apply_document(base_event(), document, "2026-08-09T10:00:00Z")
    event = result["event"]
    old = next(c for c in event["claims"] if c["id"] == "c_fact")
    new = next(c for c in event["claims"] if c["id"] == "c_correct")
    assert old["status"] == "superseded"
    assert new["status"] == "active"
    assert new["claim_role"] == "acquisition_fact"
    assert event["core_status"] == "confirmed"
    assert result["notification"]["level"] == "P0"


def test_expiry_requires_explicit_deadline():
    no_deadline = expire_event(base_event(), None, "2026-10-01T00:00:00Z")
    assert no_deadline["action"] == "noop"

    before = expire_event(base_event(), "2026-09-30T00:00:00Z", "2026-09-29T00:00:00Z")
    assert before["action"] == "noop"

    expired = expire_event(base_event(), "2026-09-30T00:00:00Z", "2026-10-01T00:00:00Z")
    assert expired["action"] == "expired"
    assert expired["event"]["lifecycle_status"] == "expired"
    assert expired["notification"]["level"] == "P1"
    assert "不写成假" in expired["event"]["summary"]


def test_empty_claims_is_duplicate_not_new_revision():
    result = apply_document(base_event(), doc(claims=[]), "2026-08-08T10:00:00Z")
    assert result["action"] == "duplicate"
    assert result["revision"] is None


def test_missing_market_evidence_keeps_impact_unverified():
    document = doc(
        claims=[
            {
                "id": "c_followup",
                "claim_type": "fact",
                "claim_role": "acquisition_fact",
                "text": "交易继续推进",
                "quote": "交易继续推进",
            }
        ]
    )
    result = apply_document(base_event(), document, "2026-08-08T10:00:00Z")
    assert result["event"]["impact_status"] == "unverified"


def test_change_type_inference():
    assert infer_change_type(doc(claims=[{"claim_type": "denial"}])) == "denial"
    assert infer_change_type(doc(claims=[{"claim_type": "correction"}])) == "correction"
    assert infer_change_type(doc(stage="sign", claims=[])) == "new_stage"
    assert infer_change_type(doc(claims=[{"claim_type": "rumor"}])) == "rumor"
