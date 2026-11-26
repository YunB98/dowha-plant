"""GET /q/{code} — docs/api-spec.md "QR 연결" 표의 모든 경우 (ADR 0013)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.metrics import QR_SCAN_FAILED
from app.models import PlantGuide, QrCode, QrScan

UTM = "utm_source=qr&utm_medium=card&utm_campaign="


@pytest.fixture
def qr(client: TestClient, db: Session) -> Iterator[None]:
    published = PlantGuide(slug="monstera", name="몬스테라", status="published")
    draft = PlantGuide(slug="calathea", name="칼라테아", status="draft")
    db.add_all([published, draft])
    db.flush()
    db.add_all(
        [
            QrCode(code="K7MP2Q", plant_guide_id=published.id),  # 정상
            QrCode(code="H8RT4W", plant_guide_id=published.id, is_active=False),  # 비활성
            QrCode(code="T3VX9N"),  # 가이드 없음
            QrCode(code="W9ZB5F", plant_guide_id=draft.id),  # 비공개 가이드
        ]
    )
    db.flush()
    yield


def get(client: TestClient, path: str):
    return client.get(path, follow_redirects=False)


def scans(db: Session, code: str) -> int:
    return db.scalar(
        select(func.count()).select_from(QrScan).join(QrCode).where(QrCode.code == code)
    )


def test_active_code_goes_to_guide(client: TestClient, db: Session, qr: None) -> None:
    res = get(client, "/q/K7MP2Q")
    assert res.status_code == 302
    assert res.headers["location"] == f"/guides/monstera/?{UTM}K7MP2Q"
    assert res.headers["cache-control"] == "no-store"
    assert scans(db, "K7MP2Q") == 1


def test_location_is_relative(client: TestClient, qr: None) -> None:
    """오리진 이름(origin.dowha-plant.shop)으로 받으므로 절대 주소를 만들면 안 된다."""
    res = client.get("/q/K7MP2Q", follow_redirects=False, headers={"Host": "origin.dowha-plant.shop"})
    assert res.headers["location"].startswith("/guides/")


def test_case_insensitive(client: TestClient, db: Session, qr: None) -> None:
    res = get(client, "/q/k7mp2q")
    assert res.headers["location"].startswith("/guides/monstera/")
    assert scans(db, "K7MP2Q") == 1


@pytest.mark.parametrize("code", ["H8RT4W", "T3VX9N", "W9ZB5F"])  # 비활성, 가이드 없음, 비공개
def test_fallback_to_guide_list_but_recorded(client: TestClient, db: Session, qr: None, code: str) -> None:
    res = get(client, f"/q/{code}")
    assert res.status_code == 302
    assert res.headers["location"] == f"/guides/?{UTM}{code}"
    assert scans(db, code) == 1


@pytest.mark.parametrize("code", ["ZZZZZZ", "abc", "0O1IL0", "%3Cscript%3E"])
def test_unknown_code_goes_to_list_without_record(client: TestClient, db: Session, qr: None, code: str) -> None:
    before = db.scalar(select(func.count()).select_from(QrScan))
    res = get(client, f"/q/{code}")
    assert res.status_code == 302
    assert res.headers["location"] == "/guides/"
    assert db.scalar(select(func.count()).select_from(QrScan)) == before


def test_record_failure_still_redirects(
    client: TestClient, db: Session, qr: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """스캔 기록이 실패해도 리디렉션은 반드시 한다."""
    def broken_commit() -> None:
        raise OperationalError("INSERT", {}, Exception("disk full"))

    monkeypatch.setattr(db, "commit", broken_commit)
    before = QR_SCAN_FAILED._value.get()

    res = get(client, "/q/K7MP2Q")
    assert res.status_code == 302
    assert res.headers["location"].startswith("/guides/monstera/")
    assert QR_SCAN_FAILED._value.get() == before + 1


def test_db_down_still_redirects(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_execute(*args: object, **kwargs: object) -> None:
        raise OperationalError("SELECT", {}, Exception("connection refused"))

    monkeypatch.setattr(db, "execute", broken_execute)
    res = get(client, "/q/K7MP2Q")
    assert res.status_code == 302
    assert res.headers["location"] == f"/guides/?{UTM}K7MP2Q"


def test_scan_metric(client: TestClient, qr: None) -> None:
    get(client, "/q/K7MP2Q")
    get(client, "/q/ZZZZZZ")
    text = client.get("/metrics/").text
    assert 'dowha_qr_scans_total{result="guide"}' in text
    assert 'dowha_qr_scans_total{result="unknown"}' in text
