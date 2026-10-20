import os
import tempfile
from pathlib import Path

os.environ["EVENTPROOF_DB"] = str(Path(tempfile.mkdtemp(prefix="eventproof-test-")) / "test.db")
os.environ["ADMIN_TOKEN"] = "test-admin-token"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


EVENT_ID = "evt_tongyu_20260805"


def client() -> TestClient:
    return TestClient(app)


def test_health_aliases():
    with client() as api:
        assert api.get("/health").status_code == 200
        assert api.get("/api/health").status_code == 200
        assert api.get("/api/health").json()["service"] == "EventProof"


def test_event_list_and_detail():
    with client() as api:
        items = api.get("/api/events").json()["items"]
        assert len(items) == 1
        assert items[0]["security_code"] == "002792"
        assert items[0]["sources_count"] == 4

        detail = api.get(f"/api/events/{EVENT_ID}").json()
        assert detail["verification_status"] == "confirmed"
        assert detail["status_detail"]["narrative"] == "denied"
        assert detail["revision"]["version"] == 4
        assert len(detail["claims"]) == 15
        assert len(detail["documents"]) == 4
        assert detail["documents"][0]["id"] == "ty_20260805_investment"
        assert detail["denied_claims_count"] == 2


def test_as_of_before_clarification():
    with client() as api:
        detail = api.get(
            f"/api/events/{EVENT_ID}",
            params={"as_of": "2026-08-06T00:00:00Z"},
        ).json()
        assert detail["revision"]["version"] == 1
        assert len(detail["claims"]) == 8
        assert detail["denied_claims_count"] == 0
        assert "3亿元" in detail["summary"]
        assert detail["status_detail"]["narrative"] == "none"


def test_as_of_rumor_then_denial():
    with client() as api:
        rumor = api.get(
            f"/api/events/{EVENT_ID}",
            params={"as_of": "2026-08-07T09:57:00Z"},
        ).json()
        assert rumor["revision"]["version"] == 2
        assert len(rumor["claims"]) == 10
        assert rumor["denied_claims_count"] == 0
        assert sum(1 for claim in rumor["claims"] if claim["status"] == "unverified") == 2
        assert rumor["status_detail"]["narrative"] == "unverified"

        denial = api.get(
            f"/api/events/{EVENT_ID}",
            params={"as_of": "2026-08-07T10:01:00Z"},
        ).json()
        assert denial["revision"]["version"] == 3
        assert denial["denied_claims_count"] == 2
        assert denial["status_detail"]["narrative"] == "denied"


def test_diff_rumor_to_denial():
    with client() as api:
        diff = api.get(
            f"/api/events/{EVENT_ID}/diff",
            params={"from_version": 2, "to_version": 3},
        ).json()
        assert len(diff["added"]) == 4
        assert len(diff["status_changes"]) == 2
        assert "denied" in diff["reason"]
        assert diff["summary_from"] != diff["summary_to"]


def test_export_traceability():
    with client() as api:
        response = api.get(f"/api/events/{EVENT_ID}/export")
        assert response.status_code == 200
        body = response.text
        assert "https://static.cninfo.com.cn/" in body
        assert "原文引用" in body
        assert "不构成投资建议" in body
        assert "qwen3.8-flash" in body


def test_notification_read_and_reset():
    headers = {"X-Admin-Token": "test-admin-token"}
    with client() as api:
        api.post("/api/demo/reset", headers=headers)
        first = api.get("/api/notifications").json()
        assert first["unread"] == 3
        notification_id = first["items"][0]["id"]
        assert api.post(f"/api/notifications/{notification_id}/read").status_code == 200
        assert api.get("/api/notifications").json()["unread"] == 2
        api.post("/api/demo/reset", headers=headers)
        assert api.get("/api/notifications").json()["unread"] == 3


def test_reset_requires_admin_token_when_configured():
    with client() as api:
        response = api.post("/api/demo/reset")
        assert response.status_code == 401


def test_scenario_correction_is_engine_driven():
    with client() as api:
        body = api.get(f"/api/events/{EVENT_ID}/scenario/correction").json()
        assert body["action"] == "updated"
        assert body["revision"]["version"] == 5
        assert body["notification"]["level"] == "P0"
        assert "2.8亿元" in body["change"]["conclusion"]
        claims = {claim["id"]: claim for claim in body["event"]["claims"]}
        assert claims["clm_ty_20260805_investment_1"]["status"] == "superseded"
        assert claims["clm_scenario_correction_amount"]["status"] == "active"
        assert body["event"]["core_status"] == "confirmed"


def test_scenario_core_denial_changes_core():
    with client() as api:
        body = api.get(f"/api/events/{EVENT_ID}/scenario/core-denial").json()
        assert body["action"] == "updated"
        assert body["event"]["core_status"] == "denied"
        assert body["notification"]["title"] == "核心收购被否认"
        assert body["notification"]["level"] == "P0"


def test_scenario_expiry_is_not_false():
    with client() as api:
        body = api.get(f"/api/events/{EVENT_ID}/scenario/expiry").json()
        assert body["action"] == "expired"
        assert body["event"]["lifecycle_status"] == "expired"
        assert body["notification"]["level"] == "P1"
        assert "不写成" in body["event"]["summary"]


def test_scenario_new_stage_is_linked_event():
    with client() as api:
        body = api.get(f"/api/events/{EVENT_ID}/scenario/new-stage").json()
        assert body["action"] == "linked_event"
        assert body["linked_event"]["linked_to"] == EVENT_ID
        assert body["revision"]["version"] == 1
        assert body["notification"]["level"] == "P1"


def test_unknown_scenario_returns_404():
    with client() as api:
        assert api.get(f"/api/events/{EVENT_ID}/scenario/nope").status_code == 404
