"""관리 요약, QR 코드 관리, 설정 관리."""

import io
from datetime import UTC, datetime, timedelta

import pytest
import zxingcpp
from fastapi.testclient import TestClient
from PIL import Image as PILImage
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import admin_qr
from app.admin_summary import month_start_kst
from app.models import Case, Inquiry, PlantGuide, QrCode, QrScan, Setting, ShowcaseItem

NOW = datetime.now(UTC)


@pytest.mark.parametrize(
    "path", ["/api/v1/admin/summary", "/api/v1/admin/qr-codes", "/api/v1/admin/qr-codes/1/image", "/api/v1/admin/settings"]
)
def test_requires_login(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 401


# ---------- 요약 ----------


def _inquiry(db: Session, status: str, created_at: datetime) -> None:
    db.add(Inquiry(type="outreach", contact_name="김", phone="010-0000-0000", status=status,
                   privacy_agreed_at=created_at, created_at=created_at))


def test_summary(admin_client: TestClient, db: Session) -> None:
    db.execute(delete(Inquiry))
    month = month_start_kst(NOW)
    _inquiry(db, "received", NOW)
    _inquiry(db, "received", month)  # 이번 달 1일 0시(한국 시간) 정각
    _inquiry(db, "contacted", month - timedelta(seconds=1))  # 지난달 마지막 순간
    _inquiry(db, "completed", NOW)

    guide = PlantGuide(slug="monstera", name="몬스테라", status="published")
    db.add_all([guide, PlantGuide(slug="draft", name="초안")])
    db.add_all([Case(title="a", organization_type="school", organization_display_name="x",
                     held_on=NOW.date(), is_published=True),
                Case(title="b", organization_type="school", organization_display_name="x", held_on=NOW.date())])
    db.add(ShowcaseItem(title="작품", is_published=True))
    db.flush()
    qr = QrCode(code="K7MP2Q", plant_guide_id=guide.id)
    db.add(qr)
    db.flush()
    db.add_all([QrScan(qr_code_id=qr.id, scanned_at=NOW - timedelta(days=d)) for d in (0, 29, 31)])
    db.flush()

    assert admin_client.get("/api/v1/admin/summary").json() == {
        "inquiries": {"received": 2, "contacted": 1, "this_month": 3},
        "qr_scans": {"last_30_days": 2},
        "content": {"cases": 1, "guides_published": 1, "showcase": 1},
    }


@pytest.mark.parametrize(
    ("now", "start"),
    [
        # UTC로는 아직 11월 30일이지만 한국은 12월 1일 오전
        (datetime(2026, 11, 30, 16, tzinfo=UTC), datetime(2026, 11, 30, 15, tzinfo=UTC)),
        (datetime(2026, 12, 15, 3, tzinfo=UTC), datetime(2026, 11, 30, 15, tzinfo=UTC)),
        (datetime(2027, 1, 1, 0, tzinfo=UTC), datetime(2026, 12, 31, 15, tzinfo=UTC)),
    ],
)
def test_month_start_is_kst(now: datetime, start: datetime) -> None:
    assert month_start_kst(now) == start


# ---------- QR 코드 ----------

QR = "/api/v1/admin/qr-codes"


@pytest.fixture
def guide(db: Session) -> PlantGuide:
    g = PlantGuide(slug="monstera", name="몬스테라", status="published")
    db.add(g)
    db.flush()
    return g


def test_create_qr_code(admin_client: TestClient, db: Session, guide: PlantGuide) -> None:
    res = admin_client.post(QR, json={"plant_guide_id": guide.id, "label": " 2026-12 몬스테라 카드 "})
    assert res.status_code == 201
    body = res.json()
    assert len(body["code"]) == 6 and set(body["code"]) <= set(admin_qr.ALPHABET)
    assert body["url"] == f"https://dowha-plant.shop/q/{body['code']}"
    assert body["label"] == "2026-12 몬스테라 카드"
    assert body["plant_guide"] == {"id": guide.id, "slug": "monstera", "name": "몬스테라", "status": "published"}
    assert (body["scans_total"], body["scans_last_30_days"], body["is_active"]) == (0, 0, True)

    # 발급한 코드로 바로 스캔된다
    scan = admin_client.get(f"/q/{body['code']}", follow_redirects=False)
    assert scan.headers["location"].startswith("/guides/monstera/")


def test_alphabet_matches_db_rule() -> None:
    import re

    from app.qr import CODE_RE

    assert all(CODE_RE.fullmatch(c * 6) for c in admin_qr.ALPHABET)
    assert not any(c in admin_qr.ALPHABET for c in "01OIL")
    assert len(admin_qr.ALPHABET) == len([c for c in "23456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" if re.fullmatch(r"[2-9A-HJKMNP-Z]", c)])


def test_create_retries_on_collision(admin_client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    db.add(QrCode(code="AAAAAA"))
    db.flush()
    codes = iter(["AAAAAA", "AAAAAA", "BBBBBB"])
    monkeypatch.setattr(admin_qr, "new_code", lambda: next(codes))
    res = admin_client.post(QR, json={})
    assert res.status_code == 201 and res.json()["code"] == "BBBBBB"


def test_create_unknown_guide(admin_client: TestClient) -> None:
    res = admin_client.post(QR, json={"plant_guide_id": 999999})
    assert res.status_code == 422


def test_list_with_scan_counts(admin_client: TestClient, db: Session, guide: PlantGuide) -> None:
    old = QrCode(code="H8RT4W", plant_guide_id=guide.id, created_at=NOW - timedelta(days=60))
    new = QrCode(code="T3VX9N", created_at=NOW)
    db.add_all([old, new])
    db.flush()
    db.add_all([QrScan(qr_code_id=old.id, scanned_at=NOW - timedelta(days=d)) for d in (1, 2, 45)])
    db.flush()

    body = admin_client.get(QR).json()
    assert [q["code"] for q in body] == ["T3VX9N", "H8RT4W"]
    assert (body[1]["scans_total"], body[1]["scans_last_30_days"]) == (3, 2)
    assert body[0]["plant_guide"] is None

    filtered = admin_client.get(f"{QR}?plant_guide_id={guide.id}").json()
    assert [q["code"] for q in filtered] == ["H8RT4W"]


def test_update_qr_code(admin_client: TestClient, db: Session, guide: PlantGuide) -> None:
    qr = QrCode(code="K7MP2Q", plant_guide_id=guide.id, label="처음")
    db.add(qr)
    db.flush()
    url = f"{QR}/{qr.id}"

    body = admin_client.patch(url, json={"is_active": False}).json()
    assert body["is_active"] is False and body["label"] == "처음" and body["plant_guide"] is not None

    body = admin_client.patch(url, json={"plant_guide_id": None, "label": "연결 해제"}).json()
    assert body["plant_guide"] is None and body["label"] == "연결 해제"

    assert admin_client.patch(url, json={"plant_guide_id": 999999}).status_code == 422
    assert admin_client.patch(url, json={"code": "ZZZZZZ"}).status_code == 422  # 코드는 바꿀 수 없다
    assert admin_client.patch(f"{QR}/999999", json={"label": "x"}).status_code == 404


def test_no_delete_endpoint(admin_client: TestClient, db: Session) -> None:
    qr = QrCode(code="K7MP2Q")
    db.add(qr)
    db.flush()
    assert admin_client.delete(f"{QR}/{qr.id}").status_code == 405
    assert db.scalar(select(QrCode).where(QrCode.id == qr.id)) is not None


def test_qr_image_png_is_readable(admin_client: TestClient, db: Session) -> None:
    """인쇄할 이미지를 실제로 디코딩해서, 스캔하면 /q/{코드}로 가는지 확인한다."""
    qr = QrCode(code="K7MP2Q")
    db.add(qr)
    db.flush()
    res = admin_client.get(f"{QR}/{qr.id}/image?size=8")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert 'filename="qr-K7MP2Q.png"' in res.headers["content-disposition"]

    image = PILImage.open(io.BytesIO(res.content))
    assert image.size == ((29 + 8) * 8,) * 2  # 버전 3(29칸) + 양쪽 여백 4칸, 칸당 8px
    decoded = zxingcpp.read_barcodes(image)
    assert [d.text for d in decoded] == ["https://dowha-plant.shop/q/K7MP2Q"]


def test_qr_image_svg(admin_client: TestClient, db: Session) -> None:
    qr = QrCode(code="K7MP2Q")
    db.add(qr)
    db.flush()
    res = admin_client.get(f"{QR}/{qr.id}/image?format=svg")
    assert res.headers["content-type"].startswith("image/svg+xml")
    assert res.text.lstrip().startswith("<?xml") and "<svg" in res.text


@pytest.mark.parametrize("query", ["format=jpg", "size=0", "size=41"])
def test_qr_image_invalid(admin_client: TestClient, db: Session, query: str) -> None:
    qr = QrCode(code="K7MP2Q")
    db.add(qr)
    db.flush()
    assert admin_client.get(f"{QR}/{qr.id}/image?{query}").status_code == 422


# ---------- 설정 ----------

SETTINGS = "/api/v1/admin/settings"


def test_get_settings(admin_client: TestClient, db: Session) -> None:
    db.merge(Setting(key="outreach.brochure_s3_key", value="files/brochure.pdf"))
    db.flush()
    body = admin_client.get(SETTINGS).json()
    assert body["contact.instagram"] == "dowha_plantshop"  # 시드 값
    assert body["contact.phone"] is None
    assert body["outreach.brochure_url"] == "https://dowha-plant.shop/files/brochure.pdf"
    assert "privacy.retention_months" not in body


def test_update_settings_and_public_store(admin_client: TestClient, db: Session) -> None:
    body = admin_client.patch(SETTINGS, json={
        "contact.phone": "01012345678",
        "contact.instagram": "@dowha_plantshop",
        "contact.kakao_url": "https://pf.kakao.com/_abc",
        "links.naver_place_url": "https://naver.me/xYz",
        "store.hours": " 10:00~19:00, 월요일 휴무 ",
    }).json()
    assert body["contact.phone"] == "010-1234-5678"  # 형식 맞춤
    assert body["contact.instagram"] == "dowha_plantshop"  # @ 제거
    assert body["store.hours"] == "10:00~19:00, 월요일 휴무"

    # 손님 화면에 바로 반영
    store = admin_client.get("/api/v1/store").json()
    assert store["contact"]["phone"] == "010-1234-5678"
    assert store["store"]["hours"] == "10:00~19:00, 월요일 휴무"


@pytest.mark.parametrize("empty", [None, ""])
def test_clear_setting(admin_client: TestClient, db: Session, empty: str | None) -> None:
    body = admin_client.patch(SETTINGS, json={"outreach.service_area": empty}).json()
    assert body["outreach.service_area"] is None
    assert db.get(Setting, "outreach.service_area") is None
    assert body["contact.instagram"] == "dowha_plantshop"  # 보내지 않은 키는 그대로


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"privacy.retention_months": 1}, "privacy.retention_months"),  # 운영 설정은 못 바꾼다
        ({"outreach.brochure_url": "https://evil.example/a.pdf"}, "outreach.brochure_url"),  # 읽기 전용
        ({"contact.phone": "1234"}, "contact.phone"),
        ({"contact.instagram": "not a handle!"}, "contact.instagram"),
        ({"contact.kakao_url": "http://pf.kakao.com/_abc"}, "contact.kakao_url"),  # https만
        ({"links.smartstore_url": "https://smartstore.naver.com.evil.example/x"}, "links.smartstore_url"),
        ({"links.naver_place_url": "https://evil.example/?naver.me"}, "links.naver_place_url"),
        ({"store.address": "x" * 201}, "store.address"),
    ],
)
def test_update_settings_invalid(admin_client: TestClient, db: Session, body: dict, field: str) -> None:
    res = admin_client.patch(SETTINGS, json=body)
    assert res.status_code == 422
    assert [d["field"] for d in res.json()["error"]["details"]] == [field]
    assert db.get(Setting, "privacy.retention_months").value == 6  # 아무것도 바뀌지 않았다


def test_subdomain_link_allowed(admin_client: TestClient) -> None:
    res = admin_client.patch(SETTINGS, json={"links.smartstore_url": "https://m.smartstore.naver.com/dowha"})
    assert res.status_code == 200
