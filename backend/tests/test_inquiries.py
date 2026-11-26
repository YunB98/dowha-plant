from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import inquiries, notify
from app.models import Inquiry, Workshop

URL = "/api/v1/inquiries"


def payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "outreach",
        "organization_name": "전주 꽃밭초등학교",
        "organization_type": "school",
        "contact_name": "김선생",
        "phone": "010 1234 5678",
        "people_count": 24,
        "audience": "children",
        "preferred_schedule": "12월 둘째 주 평일 오후",
        "location": "전주시 덕진구",
        "source": "search",
        "attribution": {"landing_referrer": "https://search.naver.com/", "utm_source": "naver"},
        "message": "다육 화분 만들기 희망",
        "privacy_agreed": True,
    }
    body.update(overrides)
    return {k: v for k, v in body.items() if v is not ...}


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """텔레그램 대신 보낸 메시지를 모은다."""
    messages: list[str] = []
    monkeypatch.setattr(inquiries, "send_telegram", messages.append)
    return messages


def count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Inquiry))


def details(res) -> dict[str, str]:
    return {d["field"]: d["message"] for d in res.json()["error"]["details"]}


def test_create(client: TestClient, db: Session, sent: list[str]) -> None:
    res = client.post(URL, json=payload())
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "received" and body["id"] > 0

    saved = db.get(Inquiry, body["id"])
    assert saved.phone == "010-1234-5678"  # 형식 통일
    assert saved.utm_source == "naver"
    assert saved.privacy_agreed_at is not None

    # 알림은 보내되 개인정보는 넣지 않는다
    assert len(sent) == 1
    assert "전주 꽃밭초등학교" in sent[0] and "24명" in sent[0]
    assert "김선생" not in sent[0] and "1234" not in sent[0]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("01012345678", "010-1234-5678"), ("02-123-4567", "02-123-4567"), ("063 271 1234", "063-271-1234")],
)
def test_phone_normalized(client: TestClient, db: Session, sent: list[str], raw: str, expected: str) -> None:
    res = client.post(URL, json=payload(phone=raw))
    assert res.status_code == 201
    assert db.get(Inquiry, res.json()["id"]).phone == expected


def test_honeypot_not_saved(client: TestClient, db: Session, sent: list[str]) -> None:
    before = count(db)
    res = client.post(URL, json=payload(website="http://spam.example"))
    assert res.status_code == 201  # 봇이 눈치채지 못하게 성공처럼
    assert count(db) == before
    assert sent == []


def test_validation_error_format(client: TestClient, sent: list[str]) -> None:
    res = client.post(URL, json=payload(phone="12345", people_count=0, organization_type="cafe", contact_name=...))
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert details(res) == {
        "phone": "연락처 형식이 올바르지 않아요. 예: 010-1234-5678",
        "people_count": "1 이상으로 입력해주세요.",
        "organization_type": "선택할 수 있는 값이 아니에요.",
        "contact_name": "필수 항목이에요.",
    }


def test_privacy_must_be_agreed(client: TestClient, sent: list[str]) -> None:
    res = client.post(URL, json=payload(privacy_agreed=False))
    assert res.status_code == 422
    assert details(res) == {"privacy_agreed": "개인정보 수집·이용에 동의해주세요."}


def test_outreach_requires_location(client: TestClient, sent: list[str]) -> None:
    res = client.post(URL, json=payload(location=None))
    assert res.status_code == 422
    assert "수업 장소" in res.json()["error"]["details"][0]["message"]

    # 매장 단체 수업은 장소가 없어도 된다
    assert client.post(URL, json=payload(type="group_visit", location=None)).status_code == 201


def test_invalid_email(client: TestClient, sent: list[str]) -> None:
    res = client.post(URL, json=payload(email="not-an-email"))
    assert details(res) == {"email": "이메일 형식이 올바르지 않아요."}


def test_unknown_workshop(client: TestClient, sent: list[str]) -> None:
    res = client.post(URL, json=payload(workshop_id=999999))
    assert res.status_code == 422
    assert details(res) == {"workshop_id": "선택한 클래스를 찾을 수 없어요."}


def test_known_workshop(client: TestClient, db: Session, sent: list[str]) -> None:
    workshop_id = db.scalar(select(Workshop.id).limit(1))
    res = client.post(URL, json=payload(workshop_id=workshop_id))
    assert res.status_code == 201


def test_unknown_field_rejected(client: TestClient, sent: list[str]) -> None:
    res = client.post(URL, json=payload(status="confirmed"))  # 손님이 상태를 정하지 못한다
    assert res.status_code == 422
    assert details(res) == {"status": "알 수 없는 항목이에요."}


def test_not_found_uses_error_format(client: TestClient) -> None:
    res = client.get("/api/v1/nope")
    assert res.status_code == 404
    assert res.json() == {"error": {"code": "NOT_FOUND", "message": "찾는 항목이 없어요."}}


def test_notification_failure_keeps_inquiry(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """텔레그램이 실패해도 문의는 저장되고 201이며, 실패는 지표에 남는다."""
    import httpx

    from app.config import get_settings
    from app.metrics import NOTIFICATIONS_FAILED

    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "1")

    def boom(*args: Any, **kwargs: Any) -> None:
        raise httpx.ConnectError("down")

    monkeypatch.setattr(notify.httpx, "post", boom)
    before = NOTIFICATIONS_FAILED.labels(channel="telegram")._value.get()

    res = client.post(URL, json=payload())
    assert res.status_code == 201
    assert db.get(Inquiry, res.json()["id"]) is not None
    assert NOTIFICATIONS_FAILED.labels(channel="telegram")._value.get() == before + 1


def test_metrics_exposed(client: TestClient, sent: list[str]) -> None:
    client.post(URL, json=payload(source="instagram"))
    text = client.get("/metrics/").text
    assert 'dowha_inquiries_created_total{source="instagram",type="outreach"}' in text
