"""Add the two official management claims (opinion + forecast) to the fixture.

These are extracted by human review from the 2026-08-05 official announcement.
They are not facts: one is a board opinion and one is a forward-looking forecast.
"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "fixtures" / "tongyu" / "precomputed.json"


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    existing = {claim["id"] for claim in data["claims"]}
    claims = [
        {
            "id": "clm_ty_20260805_investment_opinion",
            "event_id": "evt_tongyu_20260805",
            "document_id": "ty_20260805_investment",
            "text": "公司董事会认为交易价格公允、合理，符合战略布局",
            "claim_type": "opinion",
            "claim_role": "management_opinion",
            "subject": "通宇通讯",
            "predicate": "认为",
            "object": "交易价格公允、合理，符合战略布局",
            "value": None,
            "unit": "",
            "quote": "公司董事会认为，本次交易价格公允、合理，符合公司战略布局需要",
            "hedge": "management judgment",
            "confidence": 0.9,
            "status": "active",
            "strength": 86.0,
            "strength_band": "strong",
            "strength_json": {
                "authority": 0.95,
                "directness": 1.0,
                "independence": 1.0,
                "specificity": 0.6,
                "corroboration": 0.5,
                "extraction": 0.9,
            },
            "strength_explanation": "官方原文中的管理层判断；来源等级 A，但性质是观点，不能直接当事实。",
            "introduced_at": "2026-08-05T10:00:00Z",
            "is_inferred": True,
            "source_tier": "exchange",
        },
        {
            "id": "clm_ty_20260805_investment_forecast",
            "event_id": "evt_tongyu_20260805",
            "document_id": "ty_20260805_investment",
            "text": "预计下半年高毛利基站业务收入占比提升，带动盈利改善",
            "claim_type": "speculation",
            "claim_role": "management_forecast",
            "subject": "佳贤通信",
            "predicate": "预计",
            "object": "下半年高毛利基站业务收入占比提升，带动盈利改善",
            "value": None,
            "unit": "",
            "quote": "预计下半年将有所提升，带动整体盈利水平改善",
            "hedge": "forward-looking",
            "confidence": 0.9,
            "status": "active",
            "strength": 85.5,
            "strength_band": "strong",
            "strength_json": {
                "authority": 0.95,
                "directness": 1.0,
                "independence": 1.0,
                "specificity": 0.7,
                "corroboration": 0.4,
                "extraction": 0.9,
            },
            "strength_explanation": "官方预测；来源等级 A，但内容是未来判断，不代表已经实现。",
            "introduced_at": "2026-08-05T10:00:00Z",
            "is_inferred": True,
            "source_tier": "exchange",
        },
    ]
    for claim in claims:
        if claim["id"] not in existing:
            data["claims"].append(claim)

    for claim in data["claims"]:
        if claim["id"] == "clm_ty_20260805_investment_1":
            claim["slot"] = "amount"
            claim["value"] = "3亿元"

    for revision in data["revisions"]:
        ids = revision.setdefault("claim_ids", [])
        for claim_id in (
            "clm_ty_20260805_investment_opinion",
            "clm_ty_20260805_investment_forecast",
        ):
            if claim_id not in ids:
                ids.append(claim_id)

    counts = {}
    for claim in data["claims"]:
        counts[claim["document_id"]] = counts.get(claim["document_id"], 0) + 1
    for document in data["documents"]:
        document["claim_count"] = counts.get(document["id"], 0)

    data["meta"]["curation"] += (
        " 两条管理层观点/预测由人工从官方公告复核补入，未额外调用模型。"
    )
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("total_claims", len(data["claims"]))


if __name__ == "__main__":
    main()
