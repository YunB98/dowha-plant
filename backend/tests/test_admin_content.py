"""콘텐츠 관리, 사진 업로드·연결·정렬·삭제, 소개서 교체."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.main import app
from app.metrics import SITE_REBUILD_REQUESTS, UPLOADS_REJECTED
from app.models import Case, Image, Inquiry, PlantGuide, QrCode, Setting, Workshop
from app.storage import get_storage
from tests.fake_storage import FakeStorage

A = "/api/v1/admin"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 100
PDF = b"%PDF-1.7\n" + b"\x00" * 100


@pytest.fixture
def storage(admin_client: TestClient) -> Iterator[FakeStorage]:
    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_storage, None)


@pytest.fixture
def workshop(db: Session) -> Workshop:
    db.execute(delete(Workshop))
    w = Workshop(name="화분 꾸미기", price_per_person=30000, status="open")
    db.add(w)
    db.flush()
    return w


def rebuilds() -> float:
    return SITE_REBUILD_REQUESTS._value.get()


def upload(c: TestClient, storage: FakeStorage, body: bytes = JPEG, content_type: str = "image/jpeg",
           purpose: str = "image") -> str:
    """presign → (브라우저가 S3로 올렸다고 치고) tmp에 넣기 → s3_key"""
    res = c.post(f"{A}/uploads/presign", json={"purpose": purpose, "content_type": content_type, "size": len(body)})
    assert res.status_code == 200, res.text
    key = res.json()["s3_key"]
    storage.upload(key, body, content_type)
    return key


def attach(c: TestClient, storage: FakeStorage, target: str, owner_id: int, alt: str = "", **kw: object):
    key = upload(c, storage, **kw)
    return c.post(f"{A}/{target}/{owner_id}/images", json={"s3_key": key, "alt_text": alt})


# ---------- 업로드 주소 ----------


def test_presign(admin_client: TestClient, storage: FakeStorage) -> None:
    res = admin_client.post(f"{A}/uploads/presign", json={"purpose": "image", "content_type": "image/webp", "size": 2_480_000})
    body = res.json()
    assert body["s3_key"].startswith("uploads/tmp/") and body["s3_key"].endswith(".webp")
    assert body["fields"]["key"] == body["s3_key"]
    assert body["fields"]["Content-Type"] == "image/webp"
    assert body["fields"]["policy"] == f"max={10 * 1024 * 1024};exp=300"
    assert body["expires_in"] == 300


@pytest.mark.parametrize(
    "body",
    [
        {"purpose": "image", "content_type": "image/heic", "size": 100},  # 브라우저가 못 보여준다
        {"purpose": "image", "content_type": "image/gif", "size": 100},
        {"purpose": "image", "content_type": "application/pdf", "size": 100},
        {"purpose": "image", "content_type": "image/jpeg", "size": 10 * 1024 * 1024 + 1},
        {"purpose": "brochure", "content_type": "application/pdf", "size": 20 * 1024 * 1024 + 1},
        {"purpose": "video", "content_type": "video/mp4", "size": 100},
    ],
)
def test_presign_rejects(admin_client: TestClient, storage: FakeStorage, body: dict) -> None:
    assert admin_client.post(f"{A}/uploads/presign", json=body).status_code == 422


def test_presign_without_storage_config(admin_client: TestClient) -> None:
    """로컬처럼 버킷 설정이 없으면 503 (조회 API 등 나머지는 그대로 동작)."""
    res = admin_client.post(f"{A}/uploads/presign", json={"purpose": "image", "content_type": "image/jpeg", "size": 1})
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


def test_upload_requires_login(client: TestClient) -> None:
    assert client.post(f"{A}/uploads/presign", json={}).status_code == 401


# ---------- 사진 연결 ----------


def test_attach_moves_file_and_shows_publicly(
    admin_client: TestClient, storage: FakeStorage, workshop: Workshop
) -> None:
    before = rebuilds()
    res = attach(admin_client, storage, "workshops", workshop.id, alt="완성된 화분")
    assert res.status_code == 201, res.text
    image = res.json()
    assert image["image_url"].startswith(f"https://dowha-plant.shop/images/workshops/{workshop.id}/")
    assert image["sort_order"] == 0 and image["alt_text"] == "완성된 화분"

    dest = image["image_url"].removeprefix("https://dowha-plant.shop/")
    assert storage.keys() == {dest}  # tmp 원본은 지워졌다
    assert storage.objects[("media", dest)].cache_control == "public, max-age=31536000, immutable"
    assert rebuilds() == before + 1

    second = attach(admin_client, storage, "workshops", workshop.id, body=PNG, content_type="image/png").json()
    assert second["sort_order"] == 1 and second["image_url"].endswith(".png")

    public = admin_client.get(f"/api/v1/workshops/{workshop.id}").json()
    assert public["thumbnail_url"] == image["image_url"]
    assert len(public["images"]) == 2


def test_attach_webp(admin_client: TestClient, storage: FakeStorage, workshop: Workshop) -> None:
    assert attach(admin_client, storage, "workshops", workshop.id, body=WEBP, content_type="image/webp").status_code == 201


@pytest.mark.parametrize("target", ["cases", "showcase", "guides"])
def test_attach_other_targets(admin_client: TestClient, storage: FakeStorage, db: Session, target: str) -> None:
    item = {
        "cases": lambda: Case(title="t", organization_type="school", organization_display_name="x", held_on="2026-11-01"),
        "showcase": lambda: __import__("app.models", fromlist=["ShowcaseItem"]).ShowcaseItem(title="t"),
        "guides": lambda: PlantGuide(slug="monstera", name="몬스테라"),
    }[target]()
    db.add(item)
    db.flush()
    res = attach(admin_client, storage, target, item.id)
    assert res.status_code == 201
    assert f"/images/{target}/{item.id}/" in res.json()["image_url"]


@pytest.mark.parametrize(
    ("make", "reason"),
    [
        (lambda s: "images/workshops/1/aaaa.jpg", "bad_key"),  # 이미 공개된 위치를 가리키기
        (lambda s: "uploads/tmp/../../files/brochure.pdf", "bad_key"),
        (lambda s: "uploads/tmp/" + "a" * 32 + ".jpg", "missing"),  # 올리지 않음
    ],
)
def test_attach_rejects_bad_keys(admin_client: TestClient, storage: FakeStorage, workshop: Workshop, make, reason) -> None:
    before = UPLOADS_REJECTED.labels(reason=reason)._value.get()
    res = admin_client.post(f"{A}/workshops/{workshop.id}/images", json={"s3_key": make(storage)})
    assert res.status_code == 422
    assert UPLOADS_REJECTED.labels(reason=reason)._value.get() == before + 1


def _tmp(admin_client: TestClient, storage: FakeStorage, content_type: str, body: bytes, ext: str = "jpg") -> str:
    key = admin_client.post(f"{A}/uploads/presign", json={"purpose": "image", "content_type": "image/jpeg", "size": 1}).json()["s3_key"]
    key = key.rsplit(".", 1)[0] + "." + ext
    storage.upload(key, body, content_type)
    return key


@pytest.mark.parametrize(
    ("content_type", "body", "ext", "reason"),
    [
        ("image/jpeg", b"<html><script>alert(1)</script></html>", "jpg", "content"),  # 이름만 사진
        ("image/jpeg", PNG, "jpg", "content"),
        ("text/html", JPEG, "jpg", "type"),
        ("image/png", PNG, "jpg", "type"),  # 확장자와 형식 불일치
        ("image/jpeg", b"\xff\xd8\xff" + b"\x00" * (10 * 1024 * 1024), "jpg", "size"),  # 정책을 우회했다고 가정
    ],
    ids=["html-as-jpeg", "png-as-jpeg", "html-type", "ext-mismatch", "too-big"],
)
def test_attach_verifies_actual_file(
    admin_client: TestClient, storage: FakeStorage, workshop: Workshop, content_type: str, body: bytes, ext: str, reason: str
) -> None:
    key = _tmp(admin_client, storage, content_type, body, ext)
    before = UPLOADS_REJECTED.labels(reason=reason)._value.get()
    res = admin_client.post(f"{A}/workshops/{workshop.id}/images", json={"s3_key": key})
    assert res.status_code == 422, res.text
    assert UPLOADS_REJECTED.labels(reason=reason)._value.get() == before + 1
    assert storage.keys() == {key}  # 연결하지 않고 tmp에 둔다 (1일 뒤 자동 삭제)


def test_attach_unknown_owner_or_target(admin_client: TestClient, storage: FakeStorage) -> None:
    key = upload(admin_client, storage)
    assert admin_client.post(f"{A}/workshops/999999/images", json={"s3_key": key}).status_code == 404
    assert admin_client.post(f"{A}/inquiries/1/images", json={"s3_key": key}).status_code == 422


def test_attach_limit(admin_client: TestClient, storage: FakeStorage, db: Session, workshop: Workshop) -> None:
    db.add_all([Image(workshop_id=workshop.id, s3_key=f"images/workshops/x/{i}.jpg", sort_order=i) for i in range(20)])
    db.flush()
    assert attach(admin_client, storage, "workshops", workshop.id).status_code == 422


def test_copy_failure_is_503_and_nothing_saved(
    admin_client: TestClient, storage: FakeStorage, db: Session, workshop: Workshop
) -> None:
    storage.fail.add("copy")
    res = attach(admin_client, storage, "workshops", workshop.id)
    assert res.status_code == 503
    assert db.scalar(select(Image).where(Image.workshop_id == workshop.id)) is None


def test_db_failure_removes_copied_file(
    admin_client: TestClient, storage: FakeStorage, db: Session, workshop: Workshop, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = upload(admin_client, storage)

    def broken_commit() -> None:
        raise OperationalError("INSERT", {}, Exception("db down"))

    monkeypatch.setattr(db, "commit", broken_commit)
    res = admin_client.post(f"{A}/workshops/{workshop.id}/images", json={"s3_key": key})
    assert res.status_code == 503
    assert storage.keys() == {key}  # 복사본은 지우고 tmp 원본만 남는다


# ---------- 정렬·수정·삭제 ----------


@pytest.fixture
def three(admin_client: TestClient, storage: FakeStorage, workshop: Workshop) -> list[int]:
    return [attach(admin_client, storage, "workshops", workshop.id, alt=str(i)).json()["id"] for i in range(3)]


def test_reorder(admin_client: TestClient, workshop: Workshop, three: list[int]) -> None:
    new = [three[2], three[0], three[1]]
    body = admin_client.put(f"{A}/workshops/{workshop.id}/images/order", json={"image_ids": new}).json()
    assert [i["id"] for i in body] == new
    public = admin_client.get(f"/api/v1/workshops/{workshop.id}").json()
    assert public["thumbnail_url"] == body[0]["image_url"]  # 첫 번째가 대표 사진


@pytest.mark.parametrize("pick", [lambda t: t[:2], lambda t: [*t, t[0]], lambda t: [t[0], t[1], 999999]])
def test_reorder_needs_exact_ids(admin_client: TestClient, workshop: Workshop, three: list[int], pick) -> None:
    res = admin_client.put(f"{A}/workshops/{workshop.id}/images/order", json={"image_ids": pick(three)})
    assert res.status_code == 422


def test_update_alt_text(admin_client: TestClient, three: list[int]) -> None:
    body = admin_client.patch(f"{A}/images/{three[0]}", json={"alt_text": "  흰 화분에 심은 몬스테라 "}).json()
    assert body["alt_text"] == "흰 화분에 심은 몬스테라"


def test_delete_image(admin_client: TestClient, storage: FakeStorage, db: Session, three: list[int]) -> None:
    key = db.get(Image, three[0]).s3_key
    assert admin_client.delete(f"{A}/images/{three[0]}").status_code == 204
    assert db.get(Image, three[0]) is None
    assert key not in storage.keys()
    assert admin_client.delete(f"{A}/images/{three[0]}").status_code == 404


def test_delete_image_even_if_s3_fails(admin_client: TestClient, storage: FakeStorage, db: Session, three: list[int]) -> None:
    storage.fail.add("delete")
    assert admin_client.delete(f"{A}/images/{three[0]}").status_code == 204
    assert db.get(Image, three[0]) is None  # DB가 기준 (파일은 로그·지표로 남는다)


# ---------- 소개서 ----------


def test_replace_brochure(admin_client: TestClient, storage: FakeStorage, db: Session) -> None:
    key = upload(admin_client, storage, body=PDF, content_type="application/pdf", purpose="brochure")
    res = admin_client.put(f"{A}/settings/brochure", json={"s3_key": key})
    assert res.status_code == 200, res.text
    assert res.json() == {"brochure_url": "https://dowha-plant.shop/files/brochure.pdf"}
    assert storage.objects[("site", "files/brochure.pdf")].content_type == "application/pdf"
    assert key not in storage.keys("media")
    assert storage.invalidations == [["/files/brochure.pdf"]]
    assert db.get(Setting, "outreach.brochure_s3_key").value == "files/brochure.pdf"
    assert admin_client.get("/api/v1/store").json()["outreach"]["brochure_url"].endswith("/files/brochure.pdf")


def test_brochure_must_be_pdf(admin_client: TestClient, storage: FakeStorage) -> None:
    key = upload(admin_client, storage)  # 사진
    assert admin_client.put(f"{A}/settings/brochure", json={"s3_key": key}).status_code == 422


def test_brochure_invalidation_failure_still_ok(admin_client: TestClient, storage: FakeStorage) -> None:
    key = upload(admin_client, storage, body=PDF, content_type="application/pdf", purpose="brochure")
    storage.fail.add("invalidate")
    assert admin_client.put(f"{A}/settings/brochure", json={"s3_key": key}).status_code == 200


# ---------- 콘텐츠 등록·수정·삭제 ----------

CREATE = {
    "workshops": {"name": "수형 잡기", "price_per_person": 35000},
    "cases": {"title": "복지관 원예 수업", "organization_type": "welfare", "organization_display_name": "완주 ○○복지관",
              "held_on": "2026-11-02"},
    "showcase": {"title": "올리브나무 개업화분", "store_url": "https://smartstore.naver.com/dowha/products/1"},
    "guides": {"slug": "monstera", "name": "몬스테라", "watering": "겉흙이 마르면"},
}
PUBLISH = {"workshops": {"status": "open"}, "cases": {"is_published": True},
           "showcase": {"is_published": True}, "guides": {"status": "published"}}
PUBLIC_LIST = {"workshops": "/api/v1/workshops", "cases": "/api/v1/cases", "showcase": "/api/v1/showcase",
               "guides": "/api/v1/guides"}


def public_count(c: TestClient, target: str) -> int:
    body = c.get(PUBLIC_LIST[target]).json()
    return len(body["items"] if isinstance(body, dict) else body)


@pytest.mark.parametrize("target", list(CREATE))
def test_content_lifecycle(admin_client: TestClient, storage: FakeStorage, db: Session, target: str) -> None:
    db.execute(delete(Workshop))  # 시드 클래스
    before_rebuilds = rebuilds()

    created = admin_client.post(f"{A}/{target}", json=CREATE[target])
    assert created.status_code == 201, created.text
    item = created.json()
    assert public_count(admin_client, target) == 0  # 기본은 비공개
    assert rebuilds() == before_rebuilds  # 비공개 항목은 사이트를 다시 만들 필요가 없다

    listed = admin_client.get(f"{A}/{target}").json()
    assert [i["id"] for i in listed] == [item["id"]] and listed[0]["image_count"] == 0

    image = attach(admin_client, storage, target, item["id"]).json()
    published = admin_client.patch(f"{A}/{target}/{item['id']}", json=PUBLISH[target])
    assert published.status_code == 200, published.text
    assert public_count(admin_client, target) == 1
    assert rebuilds() > before_rebuilds

    detail = admin_client.get(f"{A}/{target}/{item['id']}").json()
    assert [i["id"] for i in detail["images"]] == [image["id"]]
    assert admin_client.get(f"{A}/{target}").json()[0]["thumbnail_url"] == image["image_url"]

    assert admin_client.delete(f"{A}/{target}/{item['id']}").status_code == 204
    assert admin_client.get(f"{A}/{target}/{item['id']}").status_code == 404
    assert public_count(admin_client, target) == 0
    assert storage.keys() == set()  # 사진 파일도 지웠다


@pytest.mark.parametrize("target", list(CREATE))
def test_content_requires_login_and_origin(client: TestClient, admin_client: TestClient, target: str) -> None:
    res = admin_client.post(f"{A}/{target}", json=CREATE[target], headers={"Origin": "https://evil.example"})
    assert res.status_code == 401


def test_workshop_ranges_checked_after_patch(admin_client: TestClient, workshop: Workshop) -> None:
    url = f"{A}/workshops/{workshop.id}"  # min 1, max 4
    res = admin_client.patch(url, json={"min_people": 6})
    assert res.status_code == 422 and "최소 인원" in res.json()["error"]["message"]
    assert admin_client.patch(url, json={"min_people": 6, "max_people": 10}).json()["min_people"] == 6
    assert admin_client.patch(url, json={"duration_min": 120, "duration_max": 60}).status_code == 422


@pytest.mark.parametrize(
    "body",
    [{"name": None}, {"price_per_person": -1}, {"status": "deleted"}, {"unknown": 1}, {"name": ""}, {"name": "x" * 101}],
)
def test_workshop_patch_invalid(admin_client: TestClient, workshop: Workshop, body: dict) -> None:
    assert admin_client.patch(f"{A}/workshops/{workshop.id}", json=body).status_code == 422


def test_patch_only_sent_fields(admin_client: TestClient, workshop: Workshop) -> None:
    body = admin_client.patch(f"{A}/workshops/{workshop.id}", json={"price_per_person": 32000}).json()
    assert (body["name"], body["price_per_person"], body["status"]) == ("화분 꾸미기", 32000, "open")


def test_case_workshop_link(admin_client: TestClient, db: Session, workshop: Workshop) -> None:
    body = admin_client.post(f"{A}/cases", json={**CREATE["cases"], "workshop_id": workshop.id}).json()
    assert body["workshop_id"] == workshop.id
    assert admin_client.patch(f"{A}/cases/{body['id']}", json={"workshop_id": None}).json()["workshop_id"] is None
    assert admin_client.patch(f"{A}/cases/{body['id']}", json={"workshop_id": 999999}).status_code == 422
    assert admin_client.post(f"{A}/cases", json={**CREATE["cases"], "organization_type": "army"}).status_code == 422


def test_deleting_workshop_keeps_cases_and_inquiries(admin_client: TestClient, storage: FakeStorage, db: Session,
                                                     workshop: Workshop) -> None:
    case = Case(title="t", organization_type="school", organization_display_name="x", held_on="2026-11-01",
                workshop_id=workshop.id)
    inquiry = Inquiry(type="outreach", contact_name="김", phone="010-0000-0000", workshop_id=workshop.id,
                      privacy_agreed_at="2026-11-01T00:00:00+09:00")
    db.add_all([case, inquiry])
    db.flush()
    assert admin_client.delete(f"{A}/workshops/{workshop.id}").status_code == 204
    db.expire_all()
    assert db.get(Case, case.id).workshop_id is None
    assert db.get(Inquiry, inquiry.id).workshop_id is None


def test_showcase_store_url_must_be_smartstore(admin_client: TestClient) -> None:
    res = admin_client.post(f"{A}/showcase", json={"title": "t", "store_url": "https://evil.example/shop"})
    assert res.status_code == 422


# ---------- 가이드 규칙 ----------


def test_guide_published_at_set_once(admin_client: TestClient) -> None:
    g = admin_client.post(f"{A}/guides", json=CREATE["guides"]).json()
    assert g["published_at"] is None and g["status"] == "draft"
    first = admin_client.patch(f"{A}/guides/{g['id']}", json={"status": "published"}).json()["published_at"]
    assert first is not None
    admin_client.patch(f"{A}/guides/{g['id']}", json={"status": "draft"})
    again = admin_client.patch(f"{A}/guides/{g['id']}", json={"status": "published"}).json()["published_at"]
    assert again == first


def test_guide_slug_rules(admin_client: TestClient, db: Session) -> None:
    g = admin_client.post(f"{A}/guides", json=CREATE["guides"]).json()
    url = f"{A}/guides/{g['id']}"
    # 공개 전에는 바꿀 수 있다
    assert admin_client.patch(url, json={"slug": "monstera-deliciosa"}).json()["slug"] == "monstera-deliciosa"
    # 같은 주소는 409
    dup = admin_client.post(f"{A}/guides", json={**CREATE["guides"], "slug": "monstera-deliciosa"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "CONFLICT"
    # 한 번 공개하면 비공개로 돌려도 못 바꾼다
    admin_client.patch(url, json={"status": "published"})
    admin_client.patch(url, json={"status": "draft"})
    res = admin_client.patch(url, json={"slug": "monstera-2"})
    assert res.status_code == 409
    assert admin_client.patch(url, json={"slug": "monstera-deliciosa", "name": "몬스테라 델리시오사"}).status_code == 200


@pytest.mark.parametrize("slug", ["Monstera", "monstera_1", "-monstera", "몬스테라", "a--b"])
def test_guide_slug_format(admin_client: TestClient, slug: str) -> None:
    assert admin_client.post(f"{A}/guides", json={**CREATE["guides"], "slug": slug}).status_code == 422


def test_deleting_guide_keeps_qr(admin_client: TestClient, storage: FakeStorage, db: Session) -> None:
    g = admin_client.post(f"{A}/guides", json={**CREATE["guides"], "status": "published"}).json()
    qr = QrCode(code="K7MP2Q", plant_guide_id=g["id"])
    db.add(qr)
    db.flush()
    assert admin_client.delete(f"{A}/guides/{g['id']}").status_code == 204
    db.expire_all()
    assert db.get(QrCode, qr.id).plant_guide_id is None
    scan = admin_client.get("/q/K7MP2Q", follow_redirects=False)
    assert scan.headers["location"].startswith("/guides/?")  # 인쇄된 카드는 가이드 목록으로
