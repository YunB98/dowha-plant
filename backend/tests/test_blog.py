"""블로그 RSS 가져오기, 손님 식물 API, 관리 API (ADR 0027).

RSS는 실제 네이버 블로그 RSS와 같은 구조로 만든다 (CDATA 본문 안 img, 추적 쿼리가 붙은 link, 쉼표 태그, +0900 날짜).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import blog_import
from app.blog_import import ImportAgeCollector, classify, clean_guid, parse_feed, purposes_for, run_import
from app.metrics import BLOG_THUMBNAIL_FAILED, SITE_REBUILD_REQUESTS
from app.models import BlogPost, PlantGuide, Setting
from app.purge import OverdueCollector
from tests.fake_storage import FakeStorage

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
BLOG = "https://blog.naver.com/dowha_plantshop"


def item(n: int, title: str, tags: str = "전주식물,전주개업화분,거실인테리어", desc: str = "식물을 소개합니다.",
         date: str = "Sat, 21 Nov 2026 18:49:50 +0900", image: bool = True) -> str:
    img = f'<img src="https://blogthumb.pstatic.net/{n}/image.png?type=s3" />' if image else ""
    return f"""<item>
  <author>dowha_plantshop</author><category><![CDATA[식물가게 도화]]></category>
  <title><![CDATA[{title}]]></title>
  <link><![CDATA[{BLOG}/{n}?fromRss=true&trackingCode=rss]]></link>
  <guid><![CDATA[{BLOG}/{n}?fromRss=true&trackingCode=rss]]></guid>
  <description><![CDATA[<a href="{BLOG}/{n}">{img}</a> {desc}]]></description>
  <pubDate><![CDATA[{date}]]></pubDate>
  <tag><![CDATA[{tags}]]></tag>
</item>"""


def feed(*items: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title><![CDATA[도화]]></title>{"".join(items)}</channel></rss>""".encode()


FEED = feed(
    item(103, "[전주 식물가게] 붓터치 같은 노란 무늬와 풍성 수형 | 무늬홍콩야자 키우기 및 개업 선물 추천",
         tags="무늬홍콩야자,전주개업선물,전주개업선물,거실인테리어식물"),
    item(102, "[전주 원예 출강] 전북대학교 행복드림센터 가드닝 클래스 (맞춤 출강 안내)", date="Fri, 20 Nov 2026 10:00:00 +0900"),
    item(101, "노란 팝콘 같은 봄꽃 애니시다 | 전주 식물가게 도화", date="Thu, 19 Nov 2026 10:00:00 +0900", image=False),
)


class Net:
    """가짜 네트워크: RSS와 사진 응답을 정한다. 보낸 요청의 헤더도 기록한다."""

    def __init__(self, rss: bytes = FEED, image: tuple[int, bytes] = (200, PNG), rss_status: int = 200) -> None:
        self.rss, self.image, self.rss_status = rss, image, rss_status
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == "rss.blog.naver.com":
            return httpx.Response(self.rss_status, content=self.rss)
        return httpx.Response(self.image[0], content=self.image[1])

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


@pytest.fixture(autouse=True)
def clean(db: Session) -> None:
    db.execute(delete(BlogPost))
    db.execute(delete(Setting).where(Setting.key == blog_import.LAST_OK_KEY))


# ---------- 해석과 분류 ----------


def test_parse_feed() -> None:
    items = parse_feed(FEED)
    assert [i.guid for i in items] == [f"{BLOG}/103", f"{BLOG}/102", f"{BLOG}/101"]  # 추적 쿼리 제거
    first = items[0]
    assert first.tags == ["무늬홍콩야자", "전주개업선물", "거실인테리어식물"]  # 중복 제거
    assert first.image_url == "https://blogthumb.pstatic.net/103/image.png?type=s3"
    assert first.published_at == datetime(2026, 11, 21, 9, 49, 50, tzinfo=UTC)
    assert first.excerpt == "식물을 소개합니다."  # HTML 태그 제거
    assert items[2].image_url is None


def test_parse_skips_broken_items() -> None:
    broken = feed("<item><title>제목만</title></item>", item(1, "[전주 식물가게] 정상"))
    assert [i.guid for i in parse_feed(broken)] == [f"{BLOG}/1"]


@pytest.mark.parametrize(("title", "kind"), [
    ("[전주 식물가게] 무늬홍콩야자", "plant"),
    ("[전주 개업화분] 떡갈고무나무", "plant"),  # 말머리에 단서가 없으면 식물
    ("사계절의 변화를 담는 단풍나무 3종", "plant"),  # 말머리 없음
    ("[전주 원데이클래스] 크리스마스 리스 만들기 (출강 및 단체 수업 가능)", "class"),  # 말머리가 먼저
    ("[전주 원예 출강] 도서관 가드닝 클래스", "outreach"),
    ("전주 가드닝 클래스 외부 출강 | 원예 수업", "outreach"),  # 말머리 없이 제목에서
    ("[전주 답례품 선물] 수료식 답례품", "gift"),
])
def test_classify(title: str, kind: str) -> None:
    assert classify(title) == kind


@pytest.mark.parametrize(("title", "excerpt", "expected"), [
    ("무늬홍콩야자 키우기 및 개업 선물 추천", "", ["개업·승진 선물"]),
    ("거실 플랜테리어와 개업·집들이 선물로 인기 '몬스테라'", "", ["개업·승진 선물", "집들이 선물", "거실·매장 인테리어"]),
    ("노란 팝콘 같은 봄꽃 애니시다", "", ["꽃이 피는 식물"]),
    ("전주 식물가게 도화 : 전주꽃집", "", []),  # "꽃집"은 꽃 피는 식물이 아니다
    ("프랑스고무나무", "꽃이 열매 안쪽에서 피어나 겉으로 보이지 않아요", []),  # 오판했던 실제 사례
    ("학자스민", "봄부터 꽃을 피우는 식물입니다", ["꽃이 피는 식물"]),
    ("관리가 쉬운 돈나무 금전수", "", ["키우기 쉬운 식물"]),
])
def test_purposes_from_title_not_tags(title: str, excerpt: str, expected: list[str]) -> None:
    # 검색용 태그는 모든 글에 붙어 있어서 판단에 쓰지 않는다
    assert purposes_for(title, ["전주개업화분", "거실인테리어", "집들이선물"], excerpt) == expected


@pytest.mark.parametrize(("title", "name"), [  # 실제 블로그 제목
    ("[전주 식물가게] 키우기 쉬운 공기정화식물, 동글동글 귀여운 '홍콩야자' 추천", "홍콩야자"),
    ("[전주 식물가게] 함소화 | 개업화분 집들이선물 인테리어 화분 추천", "함소화"),
    ("[전주 식물가게] 작은 잎과 열매가 매력적인 프랑스고무나무 (개업/집들이 선물 추천)", "작은 잎과 열매가 매력적인 프랑스고무나무"),
    ("노란 팝콘 같은 봄꽃 애니시다", "노란 팝콘 같은 봄꽃 애니시다"),
])
def test_default_name(title: str, name: str) -> None:
    assert blog_import.default_name(title) == name


@pytest.mark.parametrize("greeting", [
    "안녕하세요. 전주 남부시장 청년몰에 위치한 식물가게 도화입니다.",
    "안녕하세요! 전주 남부시장 청년몰에 위치한 식물가게 '도화'입니다.",
    "안녕하세요, 전주 남부시장 청년몰 식물가게 도화입니다. 🌿",
    "안녕하세요 전주 남부시장 청년몰에 위치한 도화입니다.",
])
def test_excerpt_drops_greeting(greeting: str) -> None:
    items = parse_feed(feed(item(1, "[전주 식물가게] 식물", desc=f"{greeting} 오늘은 몬스테라를 소개합니다.")))
    assert items[0].excerpt == "오늘은 몬스테라를 소개합니다."


def test_clean_guid() -> None:
    assert clean_guid(f"{BLOG}/224490215707?fromRss=true&trackingCode=rss") == f"{BLOG}/224490215707"


# ---------- 가져오기 ----------


def test_import_saves_new_posts_with_thumbnail_copies(db: Session) -> None:
    net, storage = Net(), FakeStorage()
    before = SITE_REBUILD_REQUESTS._value.get()
    result = run_import(db, net.client(), storage, now=datetime(2026, 11, 27, tzinfo=UTC))
    assert len(result.new) == 3 and result.skipped == 0

    posts = {p.guid.rsplit("/", 1)[1]: p for p in db.scalars(select(BlogPost))}
    assert posts["103"].kind == "plant" and posts["102"].kind == "outreach"
    assert posts["103"].purposes == ["개업·승진 선물"]
    assert posts["103"].thumbnail_s3_key == "images/blog/103.png"
    assert posts["101"].thumbnail_s3_key is None  # 사진이 없는 글
    assert posts["101"].id < posts["103"].id  # 오래된 글부터 넣는다
    obj = storage.objects[("media", "images/blog/103.png")]
    assert obj.content_type == "image/png" and obj.cache_control.endswith("immutable")
    # 네이버 사진은 Referer 없이 받는다 (다른 사이트 표시 차단 403)
    assert all("referer" not in r.headers for r in net.requests)
    assert db.get(Setting, blog_import.LAST_OK_KEY).value == "2026-11-27T00:00:00+00:00"
    assert SITE_REBUILD_REQUESTS._value.get() == before + 1


def test_import_is_idempotent_and_keeps_owner_edits(db: Session) -> None:
    run_import(db, Net().client(), FakeStorage())
    post = db.scalar(select(BlogPost).where(BlogPost.guid == f"{BLOG}/103"))
    post.display_name, post.sale_status, post.price, post.purposes = "무늬홍콩야자", "available", 65000, ["집들이 선물"]
    db.flush()

    before = SITE_REBUILD_REQUESTS._value.get()
    newer = feed(item(104, "[전주 식물가게] 새 식물"), item(103, "[전주 식물가게] 제목이 바뀌어도"))
    result = run_import(db, Net(rss=newer).client(), FakeStorage())
    assert len(result.new) == 1 and result.skipped == 1
    db.refresh(post)
    assert (post.display_name, post.sale_status, post.price, post.purposes) == ("무늬홍콩야자", "available", 65000, ["집들이 선물"])
    assert post.title.startswith("[전주 식물가게] 붓터치")  # 이미 있는 글은 덮어쓰지 않는다
    assert SITE_REBUILD_REQUESTS._value.get() == before + 1

    before = SITE_REBUILD_REQUESTS._value.get()
    assert run_import(db, Net(rss=newer).client(), FakeStorage()).new == []
    assert SITE_REBUILD_REQUESTS._value.get() == before  # 새 글이 없으면 재빌드 요청도 없다


@pytest.mark.parametrize(("image", "fail_put"), [((403, b"forbidden"), False), ((200, b"<html>"), False), ((200, PNG), True)],
                         ids=["naver-403", "not-image", "s3-fails"])
def test_thumbnail_failure_saves_post_without_photo(db: Session, image: tuple[int, bytes], fail_put: bool) -> None:
    storage = FakeStorage(fail={"put"} if fail_put else set())
    before = BLOG_THUMBNAIL_FAILED._value.get()
    result = run_import(db, Net(rss=feed(item(1, "[전주 식물가게] 사진 실패")), image=image).client(), storage)
    assert len(result.new) == 1 and result.thumbnails_failed == 1
    assert db.scalar(select(BlogPost.thumbnail_s3_key)) is None
    assert BLOG_THUMBNAIL_FAILED._value.get() == before + 1


def test_feed_failure_does_not_mark_success(db: Session) -> None:
    with pytest.raises(httpx.HTTPStatusError):
        run_import(db, Net(rss_status=503).client(), FakeStorage())
    assert db.get(Setting, blog_import.LAST_OK_KEY) is None
    assert db.scalar(select(BlogPost.id)) is None


def test_dry_run_writes_nothing(db: Session) -> None:
    result = run_import(db, Net().client(), FakeStorage(), dry_run=True)
    assert len(result.new) == 3
    assert db.scalar(select(BlogPost.id)) is None and db.get(Setting, blog_import.LAST_OK_KEY) is None


def test_without_storage_imports_text_only(db: Session) -> None:
    result = run_import(db, Net().client(), None)
    assert len(result.new) == 3 and result.thumbnails_failed == 0
    assert db.scalar(select(BlogPost.thumbnail_s3_key).where(BlogPost.thumbnail_s3_key.is_not(None))) is None


@contextmanager
def same_session(db: Session) -> Iterator[Session]:
    yield db


def test_cli(db: Session, capsys: pytest.CaptureFixture[str]) -> None:
    assert blog_import.main(["--dry-run"], session_factory=lambda: same_session(db), client=Net().client(), storage=FakeStorage()) == 0
    assert "새 글(저장 안 함) 3개" in capsys.readouterr().out
    assert blog_import.main([], session_factory=lambda: same_session(db), client=Net().client(), storage=FakeStorage()) == 0
    assert "새 글 3개, 이미 있음 0개" in capsys.readouterr().out


# ---------- 감시 ----------


def test_import_age_metric(db: Session) -> None:
    collector = ImportAgeCollector(lambda: same_session(db))
    assert list(collector.collect()) == []  # 아직 한 번도 가져오지 않음
    db.merge(Setting(key=blog_import.LAST_OK_KEY, value=(datetime.now(UTC) - timedelta(hours=7)).isoformat()))
    db.flush()
    age = list(collector.collect())[0].samples[0].value
    assert 7 * 3600 - 5 < age < 7 * 3600 + 60


def test_collectors_do_not_touch_db_when_registered() -> None:
    """등록할 때 DB를 조회하면 API 시작이 DB 상태에 묶인다 (DB가 늦으면 시작이 멈췄다)."""
    # 수집기는 DB 오류를 스스로 삼키므로, 예외가 없는지가 아니라 세션을 열었는지를 센다
    opened: list[str] = []

    @contextmanager
    def tracking(name: str):
        opened.append(name)
        raise OperationalError("SELECT", {}, Exception("must not be called"))
        yield

    registry = CollectorRegistry(auto_describe=True)  # 운영의 전역 REGISTRY와 같은 설정 (기본값 False면 문제가 드러나지 않는다)
    registry.register(ImportAgeCollector(lambda: tracking("blog")))
    registry.register(OverdueCollector(lambda: tracking("purge")))
    assert opened == []


# ---------- 손님 식물 API ----------


def _posts(db: Session) -> dict[str, BlogPost]:
    run_import(db, Net(rss=feed(
        item(5, "[전주 식물가게] 판매 중 식물", date="Sat, 21 Nov 2026 10:00:00 +0900"),
        item(4, "[전주 식물가게] 숨긴 식물", date="Fri, 20 Nov 2026 10:00:00 +0900"),
        item(3, "[전주 원예 출강] 출강 후기", date="Thu, 19 Nov 2026 10:00:00 +0900"),
        item(2, "[전주 식물가게] 오래된 식물 | 개업 선물 추천", date="Wed, 18 Nov 2026 10:00:00 +0900"),
    )).client(), FakeStorage())
    return {p.guid.rsplit("/", 1)[1]: p for p in db.scalars(select(BlogPost))}


def test_public_plants(client: TestClient, db: Session) -> None:
    posts = _posts(db)
    posts["4"].is_hidden = True
    draft = PlantGuide(slug="draft-guide", name="비공개", status="draft")
    live = PlantGuide(slug="monstera", name="몬스테라", status="published")
    db.add_all([draft, live])
    db.flush()
    posts["5"].plant_guide_id, posts["5"].display_name = live.id, "몬스테라"
    posts["5"].sale_status, posts["5"].price, posts["5"].size = "available", 45000, "약 40cm"
    posts["2"].plant_guide_id = draft.id
    db.flush()

    body = client.get("/api/v1/plants").json()
    assert [p["name"] for p in body] == ["몬스테라", "오래된 식물"]  # 숨김·출강 제외, 최신순, "|" 뒤 검색 문구 제거
    first = body[0]
    assert (first["sale_status"], first["price"], first["size"], first["guide_slug"]) == ("available", 45000, "약 40cm", "monstera")
    assert first["blog_url"] == f"{BLOG}/5"
    assert first["thumbnail_url"] == "https://dowha-plant.shop/images/blog/5.png"
    assert body[1]["guide_slug"] is None  # 비공개 가이드로는 연결하지 않는다
    assert body[1]["purposes"] == ["개업·승진 선물"]

    assert client.get(f"/api/v1/plants/{posts['5'].id}").json()["name"] == "몬스테라"
    for hidden in ("4", "3"):  # 숨긴 글, 식물이 아닌 글
        assert client.get(f"/api/v1/plants/{posts[hidden].id}").status_code == 404


# ---------- 관리 API ----------

ADMIN = "/api/v1/admin/blog-posts"


def test_admin_requires_login(client: TestClient) -> None:
    assert client.get(ADMIN).status_code == 401
    assert client.patch(f"{ADMIN}/1", json={"price": 1}).status_code == 401


def test_admin_list_includes_all_kinds(admin_client: TestClient, db: Session) -> None:
    posts = _posts(db)
    posts["4"].is_hidden = True
    db.flush()
    body = admin_client.get(ADMIN).json()
    assert len(body) == 4 and any(p["is_hidden"] for p in body)
    assert [p["kind"] for p in admin_client.get(f"{ADMIN}?kind=outreach").json()] == ["outreach"]


def test_admin_update(admin_client: TestClient, db: Session) -> None:
    post = _posts(db)["5"]
    guide = PlantGuide(slug="monstera", name="몬스테라", status="published")
    db.add(guide)
    db.flush()
    before = SITE_REBUILD_REQUESTS._value.get()
    body = admin_client.patch(f"{ADMIN}/{post.id}", json={
        "display_name": " 몬스테라 ", "sale_status": "reserved", "price": 45000, "size": "약 40cm",
        "purposes": ["집들이 선물", "개업·승진 선물", "집들이 선물"], "plant_guide_id": guide.id,
    }).json()
    assert body["name"] == "몬스테라" and body["sale_status"] == "reserved"
    assert body["purposes"] == ["개업·승진 선물", "집들이 선물"]  # 중복 제거, 필터 순서
    assert SITE_REBUILD_REQUESTS._value.get() == before + 1

    # 지우기: 판매 정보는 null로, 이름은 블로그 제목으로 돌아간다
    body = admin_client.patch(f"{ADMIN}/{post.id}", json={"display_name": None, "sale_status": None, "price": None, "size": None}).json()
    assert (body["display_name"], body["sale_status"], body["price"], body["size"]) == (None, None, None, "")
    assert body["name"] == "판매 중 식물"

    body = admin_client.patch(f"{ADMIN}/{post.id}", json={"kind": "other", "is_hidden": True}).json()
    assert (body["kind"], body["is_hidden"]) == ("other", True)


@pytest.mark.parametrize("payload", [
    {"purposes": ["아무 목적"]}, {"kind": None}, {"kind": "review"}, {"sale_status": "free"},
    {"price": -1}, {"plant_guide_id": 999999}, {"guid": "https://evil.example"}, {"size": "x" * 51},
])
def test_admin_update_invalid(admin_client: TestClient, db: Session, payload: dict) -> None:
    post = _posts(db)["5"]
    assert admin_client.patch(f"{ADMIN}/{post.id}", json=payload).status_code == 422


def test_admin_update_missing(admin_client: TestClient) -> None:
    assert admin_client.patch(f"{ADMIN}/999999", json={"price": 1}).status_code == 404
