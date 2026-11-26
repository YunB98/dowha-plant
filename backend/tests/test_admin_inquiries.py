"""사장님 문의 관리 — 로그인 필수, 목록은 연락처를 가리고, 상태가 바뀌면 시각을 기록한다."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.admin_inquiries import mask_email, mask_phone
from app.models import Inquiry, Workshop

BASE = "/api/v1/admin/inquiries"
T0 = datetime(2026, 11, 1, 10, tzinfo=UTC)


def make(db: Session, **kw: object) -> Inquiry:
    fields: dict[str, object] = {
        "type": "outreach",
        "organization_name": "전주 ○○초",
        "organization_type": "school",
        "contact_name": "김담당",
        "phone": "010-1234-5678",
        "people_count": 20,
        "preferred_schedule": "12월 둘째 주",
        "location": "전주",
        "source": "search",
        "privacy_agreed_at": T0,
    }
    fields.update(kw)
    inquiry = Inquiry(**fields)
    db.add(inquiry)
    db.flush()
    return inquiry


@pytest.fixture
def inquiries(db: Session) -> list[Inquiry]:
    db.execute(delete(Inquiry))
    workshop = db.query(Workshop).order_by(Workshop.id).first()
    return [
        make(db, created_at=T0, workshop_id=workshop.id if workshop else None),
        make(db, created_at=T0 + timedelta(days=1), type="group_visit", status="contacted",
             email="dowha.shop@example.com", phone=None, location=None),
        make(db, created_at=T0 + timedelta(days=2), status="completed", contact_name=None, phone=None,
             email=None, pii_purged_at=T0 + timedelta(days=3)),
    ]


# ---------- 로그인 필수 ----------


@pytest.mark.parametrize(("method", "path"), [("get", BASE), ("get", f"{BASE}/1"), ("patch", f"{BASE}/1")])
def test_requires_login(client: TestClient, method: str, path: str) -> None:
    res = getattr(client, method)(path, **({"json": {"status": "contacted"}} if method == "patch" else {}))
    assert res.status_code == 401


def test_patch_requires_same_origin(admin_client: TestClient, inquiries: list[Inquiry]) -> None:
    res = admin_client.patch(f"{BASE}/{inquiries[0].id}", json={"status": "contacted"},
                             headers={"Origin": "https://evil.example"})
    assert res.status_code == 401


# ---------- 목록 ----------


def test_list_newest_first_and_masked(admin_client: TestClient, inquiries: list[Inquiry]) -> None:
    body = admin_client.get(BASE).json()
    assert [i["id"] for i in body["items"]] == [i.id for i in reversed(inquiries)]
    assert (body["total"], body["page"], body["size"]) == (3, 1, 20)

    first, second, purged = body["items"][2], body["items"][1], body["items"][0]
    assert first["phone"] == "010-****-5678"
    assert first["contact_name"] == "김담당"
    assert first["workshop"] is not None
    assert second["email"] == "do***@example.com"
    assert purged["pii_purged"] is True and purged["contact_name"] is None
    # 목록에는 메모·요청사항 같은 긴 내용이 없다
    assert "admin_memo" not in first and "message" not in first


def test_list_filters_and_paging(admin_client: TestClient, inquiries: list[Inquiry]) -> None:
    assert [i["id"] for i in admin_client.get(f"{BASE}?status=contacted").json()["items"]] == [inquiries[1].id]
    assert [i["id"] for i in admin_client.get(f"{BASE}?type=outreach").json()["items"]] == [
        inquiries[2].id, inquiries[0].id
    ]
    page2 = admin_client.get(f"{BASE}?page=2&size=2").json()
    assert [i["id"] for i in page2["items"]] == [inquiries[0].id] and page2["total"] == 3


@pytest.mark.parametrize("query", ["status=done", "type=spam", "page=0", "size=100"])
def test_list_invalid_query(admin_client: TestClient, query: str) -> None:
    assert admin_client.get(f"{BASE}?{query}").status_code == 422


@pytest.mark.parametrize(
    ("value", "masked"),
    [("010-1234-5678", "010-****-5678"), ("02-123-4567", "02-***-4567"), ("063-123-4567", "063-***-4567"), (None, None)],
)
def test_mask_phone(value: str | None, masked: str | None) -> None:
    assert mask_phone(value) == masked


def test_mask_email() -> None:
    assert mask_email("a@b.kr") == "a***@b.kr"
    assert mask_email(None) is None


# ---------- 상세 ----------


def test_detail_has_full_contact_and_is_logged(
    admin_client: TestClient, inquiries: list[Inquiry], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO", logger="dowha.admin"):
        body = admin_client.get(f"{BASE}/{inquiries[0].id}").json()
    assert body["phone"] == "010-1234-5678"
    assert body["location"] == "전주"
    assert body["privacy_agreed_at"].startswith("2026-11-01T10:00:00")
    # 누가 어떤 문의를 봤는지 남기되, 개인정보는 로그에 넣지 않는다
    assert f"admin=owner inquiry={inquiries[0].id}" in caplog.text
    assert "010-1234-5678" not in caplog.text and "김담당" not in caplog.text


def test_detail_purged_fields_are_null(admin_client: TestClient, inquiries: list[Inquiry]) -> None:
    body = admin_client.get(f"{BASE}/{inquiries[2].id}").json()
    assert body["contact_name"] is None and body["phone"] is None and body["email"] is None
    assert body["pii_purged_at"] is not None


def test_detail_not_found(admin_client: TestClient) -> None:
    assert admin_client.get(f"{BASE}/999999").status_code == 404


# ---------- 수정 ----------


def patch(c: TestClient, inquiry: Inquiry, **body: object) -> dict:
    res = c.patch(f"{BASE}/{inquiry.id}", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def test_status_flow_records_times(admin_client: TestClient, inquiries: list[Inquiry]) -> None:
    inquiry = inquiries[0]
    contacted = patch(admin_client, inquiry, status="contacted")
    assert contacted["contacted_at"] is not None and contacted["completed_at"] is None

    quoted = patch(admin_client, inquiry, status="quoted", admin_memo="  12/3 견적서 메일 발송 ")
    assert quoted["contacted_at"] == contacted["contacted_at"]  # 처음 연락한 시각은 그대로
    assert quoted["admin_memo"] == "12/3 견적서 메일 발송"

    done = patch(admin_client, inquiry, status="completed")
    assert done["completed_at"] is not None

    canceled = patch(admin_client, inquiry, status="canceled")  # 끝난 상태끼리는 시각 유지
    assert canceled["completed_at"] == done["completed_at"]


def test_reopen_clears_completed_at(admin_client: TestClient, inquiries: list[Inquiry]) -> None:
    """다시 진행 중으로 돌리면 개인정보 보관 기간 시계를 멈춘다."""
    inquiry = inquiries[0]
    patch(admin_client, inquiry, status="canceled")
    reopened = patch(admin_client, inquiry, status="confirmed")
    assert reopened["completed_at"] is None


def test_cancel_without_contact(admin_client: TestClient, inquiries: list[Inquiry]) -> None:
    body = patch(admin_client, inquiries[0], status="canceled")
    assert body["contacted_at"] is None and body["completed_at"] is not None


def test_same_status_changes_nothing(admin_client: TestClient, inquiries: list[Inquiry]) -> None:
    first = patch(admin_client, inquiries[1], status="completed")
    again = patch(admin_client, inquiries[1], status="completed")
    assert again["completed_at"] == first["completed_at"]


def test_memo_only(admin_client: TestClient, inquiries: list[Inquiry]) -> None:
    body = patch(admin_client, inquiries[0], admin_memo="전화 안 받음, 내일 다시")
    assert body["status"] == "received" and body["contacted_at"] is None


def test_purged_inquiry_cannot_reopen(admin_client: TestClient, inquiries: list[Inquiry]) -> None:
    res = admin_client.patch(f"{BASE}/{inquiries[2].id}", json={"status": "contacted"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CONFLICT"
    # 메모는 남길 수 있다
    assert patch(admin_client, inquiries[2], admin_memo="재문의 없음")["admin_memo"] == "재문의 없음"


@pytest.mark.parametrize(
    "body", [{}, {"status": "done"}, {"admin_memo": "x" * 2001}, {"status": "contacted", "phone": "010-0000-0000"}]
)
def test_patch_invalid(admin_client: TestClient, inquiries: list[Inquiry], body: dict) -> None:
    res = admin_client.patch(f"{BASE}/{inquiries[0].id}", json=body)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_patch_not_found(admin_client: TestClient) -> None:
    assert admin_client.patch(f"{BASE}/999999", json={"status": "contacted"}).status_code == 404
