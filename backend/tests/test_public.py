"""손님용 조회 API — 공개된 것만, 정해진 순서로, 사진은 CloudFront 주소로."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event
from sqlalchemy.orm import Session

from app.models import Case, Image, PlantGuide, Setting, ShowcaseItem, Workshop

BASE = "https://dowha-plant.shop"


@pytest.fixture
def content(db: Session) -> dict[str, int]:
    """시드 클래스 3개는 지우고 테스트용 데이터로 채운다 (트랜잭션이라 끝나면 되돌아간다)."""
    db.execute(delete(Workshop))
    open_w = Workshop(name="화분 꾸미기", price_per_person=30000, sort_order=2)
    closed_w = Workshop(name="크리스마스 리스", price_per_person=40000, status="closed", is_seasonal=True, sort_order=1)
    hidden_w = Workshop(name="준비 중 클래스", price_per_person=10000, status="hidden", sort_order=0)
    db.add_all([open_w, closed_w, hidden_w])
    db.flush()

    cases = [
        Case(title="초등학교 다육 화분", organization_type="school", organization_display_name="전주 ○○초",
             held_on=date(2026, 10, 15), participant_count=20, audience="children",
             workshop_id=open_w.id, summary="아이들과 함께", is_published=True),
        Case(title="복지관 원예 수업", organization_type="welfare", organization_display_name="완주 ○○복지관",
             held_on=date(2026, 11, 2), workshop_id=hidden_w.id, is_published=True),
        Case(title="회사 행사", organization_type="company", organization_display_name="○○회사",
             held_on=date(2026, 9, 1), is_published=True),
        Case(title="비공개 사례", organization_type="school", organization_display_name="비공개",
             held_on=date(2026, 11, 20), is_published=False),
    ]
    db.add_all(cases)

    shows = [
        ShowcaseItem(title="올리브나무 개업화분", store_url="https://smartstore.naver.com/x", sort_order=1, is_published=True),
        ShowcaseItem(title="비공개 작품", sort_order=0, is_published=False),
    ]
    db.add_all(shows)

    guides = [
        PlantGuide(slug="monstera", name="몬스테라", difficulty="easy", summary="잘 자라요",
                   watering="겉흙이 마르면", status="published"),
        PlantGuide(slug="calathea", name="칼라테아", status="draft"),
    ]
    db.add_all(guides)
    db.flush()

    db.add_all(
        [
            # 대표 사진은 sort_order가 가장 작은 것 (넣은 순서와 다르게)
            Image(workshop_id=open_w.id, s3_key="images/workshops/b.webp", alt_text="두 번째", sort_order=2),
            Image(workshop_id=open_w.id, s3_key="images/workshops/a.webp", alt_text="첫 번째", sort_order=1),
            Image(case_id=cases[0].id, s3_key="images/cases/c.webp"),
            Image(showcase_item_id=shows[0].id, s3_key="images/showcase/s.webp"),
            Image(plant_guide_id=guides[0].id, s3_key="images/guides/m.webp", alt_text="몬스테라 잎"),
        ]
    )
    db.flush()
    return {
        "open": open_w.id, "closed": closed_w.id, "hidden": hidden_w.id,
        "case": cases[0].id, "case_hidden_workshop": cases[1].id, "case_private": cases[3].id,
    }


# ---------- 가게 정보 ----------


def test_store_returns_public_settings_only(client: TestClient, db: Session) -> None:
    db.merge(Setting(key="contact.phone", value="010-1234-5678"))
    db.merge(Setting(key="outreach.brochure_s3_key", value="files/brochure.pdf"))
    db.flush()

    body = client.get("/api/v1/store").json()
    assert body["contact"] == {
        "phone": "010-1234-5678", "kakao_url": None, "naver_talk_url": None, "instagram": "dowha_plantshop"
    }
    assert body["outreach"] == {"service_area": "전주, 완주, 익산", "brochure_url": f"{BASE}/files/brochure.pdf"}
    assert body["store"] == {"address": None, "hours": None}
    # 내부 설정(privacy.retention_months)은 어디에도 나오지 않는다
    assert "retention" not in str(body) and "privacy" not in body


def test_store_without_brochure(client: TestClient) -> None:
    assert client.get("/api/v1/store").json()["outreach"]["brochure_url"] is None


# ---------- 클래스 ----------


def test_workshops_excludes_hidden_and_sorts(client: TestClient, content: dict[str, int]) -> None:
    body = client.get("/api/v1/workshops").json()
    assert [w["name"] for w in body] == ["크리스마스 리스", "화분 꾸미기"]
    assert [w["status"] for w in body] == ["closed", "open"]
    assert body[1]["thumbnail_url"] == f"{BASE}/images/workshops/a.webp"
    assert body[0]["thumbnail_url"] is None
    assert "description" not in body[0] and "sort_order" not in body[0]


def test_workshop_detail_with_images(client: TestClient, content: dict[str, int]) -> None:
    body = client.get(f"/api/v1/workshops/{content['open']}").json()
    assert body["price_per_person"] == 30000
    assert [i["alt_text"] for i in body["images"]] == ["첫 번째", "두 번째"]
    assert body["images"][0]["image_url"] == f"{BASE}/images/workshops/a.webp"
    assert "s3_key" not in body["images"][0]


def test_hidden_workshop_is_404(client: TestClient, content: dict[str, int]) -> None:
    res = client.get(f"/api/v1/workshops/{content['hidden']}")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"
    assert client.get("/api/v1/workshops/999999").status_code == 404


# ---------- 진행 사례 ----------


def test_cases_published_newest_first(client: TestClient, content: dict[str, int]) -> None:
    body = client.get("/api/v1/cases").json()
    assert [c["title"] for c in body["items"]] == ["복지관 원예 수업", "초등학교 다육 화분", "회사 행사"]
    assert (body["total"], body["page"], body["size"]) == (3, 1, 20)

    school = body["items"][1]
    assert school["workshop"] == {"id": content["open"], "name": "화분 꾸미기"}
    assert school["thumbnail_url"] == f"{BASE}/images/cases/c.webp"
    assert "summary" not in school
    # 숨긴 클래스와 연결된 사례는 클래스 정보 없이
    assert body["items"][0]["workshop"] is None


def test_cases_filter_and_paging(client: TestClient, content: dict[str, int]) -> None:
    school = client.get("/api/v1/cases?organization_type=school").json()
    assert [c["title"] for c in school["items"]] == ["초등학교 다육 화분"] and school["total"] == 1

    page2 = client.get("/api/v1/cases?page=2&size=2").json()
    assert [c["title"] for c in page2["items"]] == ["회사 행사"]
    assert (page2["total"], page2["page"], page2["size"]) == (3, 2, 2)


@pytest.mark.parametrize("query", ["organization_type=hacker", "page=0", "size=51", "size=abc"])
def test_cases_invalid_query(client: TestClient, query: str) -> None:
    res = client.get(f"/api/v1/cases?{query}")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_case_detail(client: TestClient, content: dict[str, int]) -> None:
    body = client.get(f"/api/v1/cases/{content['case']}").json()
    assert body["summary"] == "아이들과 함께"
    assert len(body["images"]) == 1
    assert client.get(f"/api/v1/cases/{content['case_private']}").status_code == 404


# ---------- 작품 갤러리 ----------


def test_showcase_published_only(client: TestClient, content: dict[str, int]) -> None:
    body = client.get("/api/v1/showcase").json()
    assert [s["title"] for s in body] == ["올리브나무 개업화분"]
    assert body[0]["images"][0]["image_url"] == f"{BASE}/images/showcase/s.webp"


# ---------- 식물 가이드 ----------


def test_guides_published_only(client: TestClient, content: dict[str, int]) -> None:
    body = client.get("/api/v1/guides").json()
    assert body == [
        {"slug": "monstera", "name": "몬스테라", "difficulty": "easy", "summary": "잘 자라요",
         "thumbnail_url": f"{BASE}/images/guides/m.webp"}
    ]


def test_guide_detail_and_draft_404(client: TestClient, content: dict[str, int]) -> None:
    body = client.get("/api/v1/guides/monstera").json()
    assert body["watering"] == "겉흙이 마르면"
    assert body["images"][0]["alt_text"] == "몬스테라 잎"
    assert "status" not in body and "id" not in body
    assert client.get("/api/v1/guides/calathea").status_code == 404
    assert client.get("/api/v1/guides/nothing").status_code == 404


# ---------- 쿼리 수 ----------


def test_list_queries_do_not_grow_with_items(client: TestClient, db: Session, content: dict[str, int]) -> None:
    """사진을 항목마다 따로 읽지 않는다 (목록 1번 + 사진 1번 + 개수 1번)."""
    for i in range(10):
        db.add(Case(title=f"추가 {i}", organization_type="other", organization_display_name="x",
                    held_on=date(2026, 1, 1), is_published=True))
    db.flush()

    statements: list[str] = []
    engine = db.get_bind().engine
    listener = lambda *args: statements.append(args[2])  # noqa: E731
    event.listen(engine, "before_cursor_execute", listener)
    try:
        assert len(client.get("/api/v1/cases").json()["items"]) == 13
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) <= 3, selects


def test_public_base_url_setting(client: TestClient, content: dict[str, int], monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "public_base_url", "http://localhost:3000/")
    body = client.get("/api/v1/guides").json()
    assert body[0]["thumbnail_url"] == "http://localhost:3000/images/guides/m.webp"
