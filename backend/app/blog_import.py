"""네이버 블로그 RSS 가져오기 (ADR 0027, 기능명세 S-01).

사장님은 지금처럼 블로그에만 글을 쓴다. 이 작업이 한 시간마다 RSS를 읽어 새 글을 blog_posts에 넣는다.
- RSS에는 제목·앞부분 약 340자·태그·대표 사진(365px) 한 장만 있다. 전체 글은 블로그로 연결한다
- 대표 사진은 네이버가 다른 사이트에서 직접 표시하는 것을 막아서(403) 서버가 받아 S3에 사본을 둔다
- 제목 말머리로 분류한다: [전주 식물가게] 식물, [… 원데이클래스] 클래스, [… 출강] 출강 사례, [… 답례품] 단체 선물
- 블로그 태그(검색용, 중복 많음)를 사이트의 목적 필터 6개로 정리한다
- 이미 있는 글은 건드리지 않는다 (사장님이 관리 화면에서 고친 값을 덮어쓰지 않게)

실행: 서버 systemd 타이머가 매시간 (deploy/systemd/dowha-blog-import.*)
    docker compose exec -T api python -m app.blog_import            # 가져오기
    docker compose exec -T api python -m app.blog_import --dry-run  # 새 글 수만 보기

감시: 마지막으로 성공한 시각을 settings blog.last_import_ok_at에 남기고, API /metrics가
dowha_blog_import_age_seconds로 내보낸다. 6시간 넘게 성공하지 못하면 경보(BlogImportStale).
"""

import argparse
import html
import logging
import re
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree

import httpx
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.metrics import BLOG_IMPORTED, BLOG_THUMBNAIL_FAILED
from app.models import BlogPost, Setting
from app.site_rebuild import request_rebuild
from app.storage import Storage, StorageError

log = logging.getLogger("dowha.blog")

LAST_OK_KEY = "blog.last_import_ok_at"
USER_AGENT = "dowha-blog-import/1.0 (+https://dowha-plant.shop)"
MAX_FEED_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_CACHE = "public, max-age=31536000, immutable"

# 사이트 목적 필터 (frontend/lib/demo.ts PURPOSES와 같은 이름)
PURPOSES = ("개업·승진 선물", "집들이 선물", "거실·매장 인테리어", "키우기 쉬운 식물", "꽃이 피는 식물", "단체 답례품")

# 목적별 단서. 제목에서만 찾는다 (꽃 피는 식물만 요약도 본다).
# 블로그 태그는 검색용이라 "전주개업화분", "거실인테리어"가 거의 모든 글에 붙는다.
# 실제 글 50개로 확인: 태그까지 보면 40개가 "거실·매장 인테리어", 38개가 "개업·승진 선물"이 되어 필터가 의미 없었다
PURPOSE_RULES: dict[str, tuple[str, ...]] = {
    "개업·승진 선물": ("개업", "승진", "축하"),
    "집들이 선물": ("집들이",),
    "거실·매장 인테리어": ("거실", "인테리어", "플랜테리어", "매장"),
    "키우기 쉬운 식물": ("키우기 쉬운", "키우기쉬운", "초보", "관리가 쉬운", "관리가 쉽"),
    "꽃이 피는 식물": ("꽃", "카네이션", "작약", "개화"),
    "단체 답례품": ("답례품", "단체선물", "단체 선물"),
}
FLOWER_EXCERPT = ("꽃을 피우", "꽃을 피워", "꽃이 피는", "꽃이 핍니다")  # "열매 안쪽에서 피어나"는 꽃 피는 식물이 아니다
NOT_FLOWER = ("꽃집",)

# 분류 단서 (위에서부터 먼저 맞는 것). 말머리를 먼저 보고, 말머리에 단서가 없으면 제목 전체를 본다.
# 단서가 없으면 식물이다 (도화 블로그의 기본은 식물 소개). 실제 글 50개 중 13개가 말머리가 없거나 달랐다
KIND_RULES: tuple[tuple[str, str], ...] = (
    ("출강", "outreach"),
    ("클래스", "class"),
    ("원데이", "class"),
    ("답례품", "gift"),
)
PREFIX_RE = re.compile(r"^\s*\[([^\]]{1,40})\]\s*")
# 제목에 따옴표로 감싼 식물 이름: '홍콩야자', ‘아랄리아’, "몬스테라"
QUOTED_RE = re.compile(r"""['‘"“]([^'’"”]{2,30})['’"”]""")
TRAILING_PAREN_RE = re.compile(r"\s*\([^()]*\)\s*$")
# 모든 글이 인사로 시작한다. 실제 변형: "안녕하세요. 전주 남부시장 청년몰에 위치한 식물가게 도화입니다.",
# "안녕하세요! … '도화'입니다.", "안녕하세요, … 식물가게입니다." → "안녕하세요 … 입니다." 첫 문장을 뗀다
GREETING_RE = re.compile(r"^\s*안녕하세요[.!,]?\s*[^.!?]{0,50}?입니다[.!]?\s*(?:🌿)?\s*")
IMG_RE = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.I)
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class FeedItem:
    guid: str
    title: str
    excerpt: str
    tags: list[str]
    published_at: datetime
    image_url: str | None


@dataclass
class ImportResult:
    new: list[str] = field(default_factory=list)  # 새로 넣은 guid
    skipped: int = 0  # 이미 있던 글
    thumbnails_failed: int = 0


# ---------- 해석 ----------


def clean_guid(link: str) -> str:
    """https://blog.naver.com/dowha_plantshop/224490215707?fromRss=true&trackingCode=rss → 쿼리 없는 주소"""
    p = urlsplit(link.strip())
    return urlunsplit((p.scheme or "https", p.netloc, p.path.rstrip("/"), "", ""))


def strip_html(s: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub(" ", s)).split())


def classify(title: str) -> str:
    m = PREFIX_RE.match(title)
    for text in ([m.group(1)] if m else []) + [title]:
        for word, kind in KIND_RULES:
            if word in text:
                return kind
    return "plant"


def purposes_for(title: str, tags: Iterable[str], excerpt: str) -> list[str]:
    """tags는 받지만 쓰지 않는다 (검색용 태그가 모든 글에 붙어 있어서). 사장님이 관리 화면에서 고칠 수 있다"""
    t = title
    for word in NOT_FLOWER:
        t = t.replace(word, "")
    found = {p for p in PURPOSES if any(clue in t for clue in PURPOSE_RULES[p])}
    if any(c in excerpt for c in FLOWER_EXCERPT):
        found.add("꽃이 피는 식물")
    return [p for p in PURPOSES if p in found]  # 필터 순서대로


def clean_title(title: str) -> str:
    """말머리를 떼어 낸 제목"""
    return PREFIX_RE.sub("", title).strip()


def default_name(title: str) -> str:
    """화면에 보일 이름의 기본값. 사장님이 짧은 이름(display_name)을 정하면 그것을 쓴다.
    블로그 제목이 길어(최대 70자 정도) 상세 페이지 제목이 여러 줄이 됐다. 실제 제목 다수가 식물 이름을
    따옴표로 감싸고 있어 그것을 먼저 쓰고, 없으면 끝의 괄호 설명만 뗀다."""
    t = clean_title(title)
    m = QUOTED_RE.search(t)
    if m:
        return m.group(1).strip()
    # "함소화 | 개업화분 집들이선물 인테리어 화분 추천": | 뒤는 대부분 검색용 문구다
    head = t.split(" | ", 1)[0]
    return TRAILING_PAREN_RE.sub("", head).strip() or t


def parse_feed(data: bytes) -> list[FeedItem]:
    root = ElementTree.fromstring(data)
    channel = root.find("channel")
    items: list[FeedItem] = []
    for it in (channel.findall("item") if channel is not None else []):
        link = (it.findtext("link") or it.findtext("guid") or "").strip()
        title = " ".join((it.findtext("title") or "").split())
        date = it.findtext("pubDate")
        if not link or not title or not date:
            log.warning("blog item skipped (missing link/title/date): %r", title[:60])
            continue
        desc = it.findtext("description") or ""
        img = IMG_RE.search(desc)
        tags = list(dict.fromkeys(t.strip() for t in (it.findtext("tag") or "").split(",") if t.strip()))
        published = parsedate_to_datetime(date)
        items.append(FeedItem(
            guid=clean_guid(link)[:300],
            title=title[:300],
            excerpt=GREETING_RE.sub("", strip_html(desc))[:1000],
            tags=tags[:50],
            published_at=published if published.tzinfo else published.replace(tzinfo=UTC),
            image_url=html.unescape(img.group(1)) if img else None,
        ))
    return items


# ---------- 대표 사진 ----------

IMAGE_TYPES = ((b"\xff\xd8\xff", "jpg", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "png", "image/png"))


def image_kind(head: bytes) -> tuple[str, str] | None:
    for magic, ext, ctype in IMAGE_TYPES:
        if head.startswith(magic):
            return ext, ctype
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


def copy_thumbnail(client: httpx.Client, storage: Storage, item: FeedItem) -> str | None:
    """네이버 대표 사진을 받아 S3 images/blog/에 사본을 둔다. 실패하면 None (글은 사진 없이 저장)."""
    if not item.image_url or not item.image_url.startswith("https://"):
        return None
    try:
        res = client.get(item.image_url)  # Referer를 보내지 않는다 (네이버가 다른 사이트 표시를 403으로 막는다)
        res.raise_for_status()
        body = res.content
        if len(body) > MAX_IMAGE_BYTES:
            raise ValueError(f"too large: {len(body)} bytes")
        kind = image_kind(body[:16])
        if kind is None:
            raise ValueError("not an image")
        ext, ctype = kind
        post_id = item.guid.rsplit("/", 1)[-1]
        key = f"images/blog/{re.sub(r'[^0-9A-Za-z_-]', '', post_id) or 'post'}.{ext}"
        storage.put(storage.media_bucket, key, body, ctype, IMAGE_CACHE)
        return key
    except (httpx.HTTPError, ValueError, StorageError) as e:
        BLOG_THUMBNAIL_FAILED.inc()
        log.warning("blog thumbnail failed: %s (%s)", item.guid, e)
        return None


# ---------- 가져오기 ----------


def fetch_feed(client: httpx.Client, url: str) -> bytes:
    res = client.get(url)
    res.raise_for_status()
    if len(res.content) > MAX_FEED_BYTES:
        raise ValueError(f"RSS too large: {len(res.content)} bytes")
    return res.content


def run_import(db: Session, client: httpx.Client, storage: Storage | None, *, dry_run: bool = False,
               now: datetime | None = None) -> ImportResult:
    items = parse_feed(fetch_feed(client, get_settings().blog_rss_url))
    existing = set(db.scalars(select(BlogPost.guid).where(BlogPost.guid.in_([i.guid for i in items]))))
    result = ImportResult(skipped=len(existing))
    new_items = [i for i in items if i.guid not in existing]
    if dry_run:
        result.new = [i.guid for i in new_items]
        return result

    for item in reversed(new_items):  # 오래된 글부터 넣는다 (id가 올린 순서를 따르게)
        key = copy_thumbnail(client, storage, item) if storage else None
        if storage and item.image_url and key is None:
            result.thumbnails_failed += 1
        db.add(BlogPost(
            guid=item.guid, title=item.title, excerpt=item.excerpt,
            kind=classify(item.title), tags=item.tags, purposes=purposes_for(item.title, item.tags, item.excerpt),
            thumbnail_s3_key=key, published_at=item.published_at,
        ))
        result.new.append(item.guid)

    db.merge(Setting(key=LAST_OK_KEY, value=(now or datetime.now(UTC)).isoformat(), description="블로그 RSS를 마지막으로 가져온 시각"))
    db.commit()
    BLOG_IMPORTED.inc(len(result.new))
    log.info("blog import: new=%d skipped=%d thumbnails_failed=%d", len(result.new), result.skipped, result.thumbnails_failed)
    if result.new:
        request_rebuild(f"blog import: {len(result.new)} new posts")
    return result


# ---------- 감시 ----------


class ImportAgeCollector(Collector):
    """마지막 성공 후 지난 초. 아직 한 번도 성공하지 않았으면 내보내지 않는다."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def describe(self) -> Iterable[GaugeMetricFamily]:  # 등록할 때 DB를 조회하지 않게 (purge.OverdueCollector 참고)
        yield GaugeMetricFamily("dowha_blog_import_age_seconds", "")

    def collect(self) -> Iterable[GaugeMetricFamily]:
        try:
            with self.session_factory() as db:
                value = db.scalar(select(Setting.value).where(Setting.key == LAST_OK_KEY))
        except SQLAlchemyError:
            log.warning("blog import age read failed", exc_info=True)
            return
        if not value:
            return
        try:
            age = (datetime.now(UTC) - datetime.fromisoformat(value)).total_seconds()
        except (TypeError, ValueError):
            return
        yield GaugeMetricFamily("dowha_blog_import_age_seconds", "블로그 RSS를 마지막으로 가져온 뒤 지난 초", value=max(0.0, age))


# ---------- 실행 ----------


def main(argv: Sequence[str] | None = None, session_factory: Callable[[], Session] | None = None,
         client: httpx.Client | None = None, storage: Storage | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.blog_import", description="블로그 RSS에서 새 글 가져오기")
    parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 새 글 수만 출력")
    args = parser.parse_args(argv)

    if session_factory is None:
        from app.db import SessionLocal

        session_factory = SessionLocal
    if storage is None and get_settings().media_bucket:
        from app.storage import _s3

        storage = _s3()
    own_client = client is None
    client = client or httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    try:
        with session_factory() as db:
            r = run_import(db, client, storage, dry_run=args.dry_run)
    finally:
        if own_client:
            client.close()
    word = "새 글(저장 안 함)" if args.dry_run else "새 글"
    print(f"{word} {len(r.new)}개, 이미 있음 {r.skipped}개" + (f", 사진 실패 {r.thumbnails_failed}개" if r.thumbnails_failed else ""))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    sys.exit(main())
