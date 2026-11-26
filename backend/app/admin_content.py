"""사장님 콘텐츠 관리: 클래스, 진행 사례, 작품 갤러리, 식물 가이드 (docs/api-spec.md 2장 "콘텐츠").

네 가지 모두 같은 모양이다: 목록(비공개 포함), 상세, 등록, 수정(보낸 필드만), 삭제.
- 새로 만들면 비공개(hidden, draft, is_published=false)가 기본. 사진을 다 올린 뒤 공개한다
- 범위 검사(최소 인원 ≤ 최대 인원 등)는 수정 후 값으로 다시 한다. DB CHECK에 맡기면 500이 된다
- 공개 내용이 바뀌면 사이트 재빌드를 요청한다 (ADR 0015, site_rebuild)
- 삭제하면 사진 파일도 지운다 (DB는 CASCADE로 지워지지만 S3 파일은 남기 때문)
- 가이드: 처음 공개할 때 published_at 기록. 한 번이라도 공개된 가이드는 slug를 바꿀 수 없다 (409).
  검색 결과·공유된 링크가 깨지기 때문이다. QR은 slug가 아니라 id로 연결되어 영향이 없다
"""

import logging
import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator
from pydantic.fields import FieldInfo
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin_settings import _check_link
from app.admin_uploads import OWNERS, ImageOut, delete_files, image_out, images_of
from app.auth import current_admin
from app.db import get_db
from app.models import Base, Case, Image, PlantGuide, ShowcaseItem, Workshop
from app.site_rebuild import request_rebuild
from app.storage import Storage, get_storage

router = APIRouter(prefix="/api/v1/admin", tags=["admin-content"], dependencies=[Depends(current_admin)])
log = logging.getLogger("dowha.admin")

OrganizationType = Literal["school", "kindergarten", "welfare", "public", "company", "other"]
Audience = Literal["children", "teens", "adults", "seniors", "mixed"]


def Text() -> Any:  # noqa: N802  (긴 글 필드: 기본 빈 문자열, 5000자 이하)
    return Field("", max_length=5000)

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------- 입력 형식 (등록: 필수값 있음 / 수정: 모두 선택) ----------


class WorkshopIn(Input):
    name: str = Field(min_length=1, max_length=100)
    description: str = Text()
    price_per_person: int = Field(ge=0, le=10_000_000)
    min_people: int = Field(1, ge=1, le=1000)
    max_people: int = Field(4, ge=1, le=1000)
    duration_min: int = Field(60, ge=1, le=600)
    duration_max: int = Field(90, ge=1, le=600)
    is_seasonal: bool = False
    supports_outreach: bool = True
    status: Literal["open", "closed", "hidden"] = "hidden"
    sort_order: int = Field(0, ge=0, le=10_000)


class CaseIn(Input):
    title: str = Field(min_length=1, max_length=100)
    organization_type: OrganizationType
    organization_display_name: str = Field(min_length=1, max_length=100)
    held_on: date
    participant_count: int | None = Field(None, ge=1, le=10_000)
    audience: Audience | None = None
    workshop_id: int | None = None
    summary: str = Text()
    is_published: bool = False


class ShowcaseIn(Input):
    title: str = Field(min_length=1, max_length=100)
    description: str = Text()
    store_url: str | None = Field(None, max_length=500)
    sort_order: int = Field(0, ge=0, le=10_000)
    is_published: bool = False

    @field_validator("store_url")
    @classmethod
    def _store_url(cls, v: str | None) -> str | None:
        return _check_link("links.smartstore_url", v) if v else None


class GuideIn(Input):
    slug: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=100)
    scientific_name: str | None = Field(None, max_length=150)
    difficulty: Literal["easy", "normal", "hard"] = "normal"
    summary: str = Text()
    light: str = Text()
    watering: str = Text()
    temperature: str = Text()
    humidity: str = Text()
    seasonal_care: str = Text()
    troubleshooting: str = Text()
    status: Literal["draft", "published"] = "draft"

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str | None) -> str | None:
        if v is not None and not SLUG_RE.fullmatch(v):
            raise ValueError("영문 소문자·숫자·하이픈만 쓸 수 있어요. 예: monstera-deliciosa")
        return v


def optional(model: type[Input]) -> type[Input]:
    """수정용: 같은 필드·검증(상속), 모두 선택. 보낸 필드만 바꾼다 (model_fields_set)."""
    fields: dict[str, Any] = {
        name: (info.annotation | None, FieldInfo.merge_field_infos(info, default=None))
        for name, info in model.model_fields.items()
    }
    return create_model(f"{model.__name__.removesuffix('In')}Patch", __base__=model, **fields)


# ---------- 공통 ----------

# NULL로 비울 수 있는 필드 (나머지는 null을 보내면 422)
NULLABLE = {"participant_count", "audience", "workshop_id", "store_url", "scientific_name"}


def changes(body: Input) -> dict[str, Any]:
    data = {k: getattr(body, k) for k in body.model_fields_set}
    bad = [k for k, v in data.items() if v is None and k not in NULLABLE]
    if bad:
        raise HTTPException(status_code=422, detail=f"비울 수 없는 항목이에요: {', '.join(sorted(bad))}")
    return data


def check_ranges(item: Base) -> None:
    if isinstance(item, Workshop):
        if item.min_people > item.max_people:
            raise HTTPException(status_code=422, detail="최소 인원이 최대 인원보다 많아요.")
        if item.duration_min > item.duration_max:
            raise HTTPException(status_code=422, detail="최소 시간이 최대 시간보다 길어요.")


def check_workshop(db: Session, workshop_id: int | None) -> None:
    if workshop_id is not None and db.get(Workshop, workshop_id) is None:
        raise HTTPException(status_code=422, detail="연결할 클래스가 없어요.")


def save(db: Session, item: Base) -> None:
    check_ranges(item)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if "uq_plant_guides_slug" in str(e.orig):
            raise HTTPException(status_code=409, detail="이미 쓰고 있는 주소(slug)예요.") from None
        raise HTTPException(status_code=422) from None
    db.refresh(item)


def thumbnails(db: Session, target: str, ids: list[int]) -> dict[int, tuple[str | None, int]]:
    """항목별 (대표 사진 주소, 사진 수). 한 번에 읽는다."""
    from app.public import public_url

    column = OWNERS[target].column
    result: dict[int, tuple[str | None, int]] = {i: (None, 0) for i in ids}
    if not ids:
        return result
    rows = db.execute(select(column, Image.s3_key).where(column.in_(ids)).order_by(column, Image.sort_order, Image.id))
    for owner_id, key in rows:
        url, n = result[owner_id]
        result[owner_id] = (url or public_url(key), n + 1)
    return result


def fields_of(item: Base, names: list[str]) -> dict[str, Any]:
    return {n: getattr(item, n) for n in names}


# ---------- 출력 형식 ----------


class Listed(BaseModel):
    id: int
    title: str  # 클래스·가이드는 name
    status: str  # open/closed/hidden, draft/published, published/hidden
    thumbnail_url: str | None
    image_count: int
    updated_at: datetime


class WorkshopOut(WorkshopIn):
    id: int
    images: list[ImageOut]
    created_at: datetime
    updated_at: datetime


class CaseOut(CaseIn):
    id: int
    images: list[ImageOut]
    created_at: datetime
    updated_at: datetime


class ShowcaseOut(ShowcaseIn):
    id: int
    images: list[ImageOut]
    created_at: datetime
    updated_at: datetime


class GuideOut(GuideIn):
    id: int
    published_at: datetime | None
    images: list[ImageOut]
    created_at: datetime
    updated_at: datetime


# ---------- 종류별 설정 ----------


class Kind:
    def __init__(self, target: str, model: type[Base], create: type[Input], out: type[BaseModel],
                 title: Callable[[Any], str], status: Callable[[Any], str], order: list[Any],
                 is_public: Callable[[Any], bool]) -> None:
        self.target, self.model, self.create, self.out = target, model, create, out
        self.patch = optional(create)
        self.title, self.status, self.order, self.is_public = title, status, order, is_public
        self.fields = [n for n in out.model_fields if n not in ("images",)]


KINDS = {
    "workshops": Kind("workshops", Workshop, WorkshopIn, WorkshopOut, lambda w: w.name, lambda w: w.status,
                      [Workshop.sort_order, Workshop.id], lambda w: w.status != "hidden"),
    "cases": Kind("cases", Case, CaseIn, CaseOut, lambda c: c.title,
                  lambda c: "published" if c.is_published else "hidden",
                  [Case.held_on.desc(), Case.id.desc()], lambda c: c.is_published),
    "showcase": Kind("showcase", ShowcaseItem, ShowcaseIn, ShowcaseOut, lambda s: s.title,
                     lambda s: "published" if s.is_published else "hidden",
                     [ShowcaseItem.sort_order, ShowcaseItem.id], lambda s: s.is_published),
    "guides": Kind("guides", PlantGuide, GuideIn, GuideOut, lambda g: g.name, lambda g: g.status,
                   [PlantGuide.name, PlantGuide.id], lambda g: g.status == "published"),
}


def detail(db: Session, kind: Kind, item: Base) -> BaseModel:
    images = [image_out(i) for i in images_of(db, kind.target, item.id)]
    return kind.out(**fields_of(item, kind.fields), images=images)


def get_or_404(db: Session, kind: Kind, item_id: int) -> Base:
    item = db.get(kind.model, item_id)
    if item is None:
        raise HTTPException(status_code=404)
    return item


def apply_guide_rules(item: PlantGuide, data: dict[str, Any]) -> None:
    if "slug" in data and data["slug"] != item.slug and item.published_at is not None:
        raise HTTPException(status_code=409, detail="한 번 공개한 가이드의 주소(slug)는 바꿀 수 없어요.")
    if data.get("status") == "published" and item.published_at is None:
        item.published_at = datetime.now(UTC)


# ---------- 라우트 (네 종류에 같은 함수를 붙인다) ----------


def register(kind: Kind) -> None:
    base = f"/{kind.target}"
    tag = [f"admin-{kind.target}"]

    @router.get(base, tags=tag, name=f"list_{kind.target}")
    def list_items(db: Session = Depends(get_db)) -> list[Listed]:
        items = db.scalars(select(kind.model).order_by(*kind.order)).all()
        thumbs = thumbnails(db, kind.target, [i.id for i in items])
        return [Listed(id=i.id, title=kind.title(i), status=kind.status(i), thumbnail_url=thumbs[i.id][0],
                       image_count=thumbs[i.id][1], updated_at=i.updated_at) for i in items]

    @router.get(f"{base}/{{item_id}}", tags=tag, name=f"get_{kind.target}")
    def get_item(item_id: int, db: Session = Depends(get_db)) -> kind.out:  # type: ignore[name-defined]
        return detail(db, kind, get_or_404(db, kind, item_id))

    @router.post(base, status_code=201, tags=tag, name=f"create_{kind.target}")
    def create_item(body: kind.create, db: Session = Depends(get_db)) -> kind.out:  # type: ignore[name-defined]
        data = body.model_dump()
        check_workshop(db, data.get("workshop_id"))
        item = kind.model()
        if isinstance(item, PlantGuide):
            apply_guide_rules(item, data)
        for k, v in data.items():
            setattr(item, k, v)
        db.add(item)
        save(db, item)
        log.info("content created: %s/%d", kind.target, item.id)
        if kind.is_public(item):
            request_rebuild(f"{kind.target}/{item.id} created")
        return detail(db, kind, item)

    @router.patch(f"{base}/{{item_id}}", tags=tag, name=f"update_{kind.target}")
    def update_item(item_id: int, body: kind.patch, db: Session = Depends(get_db)) -> kind.out:  # type: ignore[name-defined]
        item = get_or_404(db, kind, item_id)
        data = changes(body)
        if "workshop_id" in data:
            check_workshop(db, data["workshop_id"])
        was_public = kind.is_public(item)
        if isinstance(item, PlantGuide):
            apply_guide_rules(item, data)
        for k, v in data.items():
            setattr(item, k, v)
        save(db, item)
        log.info("content updated: %s/%d fields=%s", kind.target, item.id, ",".join(sorted(data)))
        if was_public or kind.is_public(item):  # 공개 중이거나, 공개되거나, 내려갈 때
            request_rebuild(f"{kind.target}/{item.id} updated")
        return detail(db, kind, item)

    @router.delete(f"{base}/{{item_id}}", status_code=204, tags=tag, name=f"delete_{kind.target}")
    def delete_item(item_id: int, db: Session = Depends(get_db), storage: Storage = Depends(get_storage)) -> None:
        item = get_or_404(db, kind, item_id)
        was_public = kind.is_public(item)
        keys = [i.s3_key for i in images_of(db, kind.target, item.id)]
        db.delete(item)  # 사진 행은 CASCADE, 연결된 사례·문의·QR은 SET NULL
        db.commit()
        delete_files(storage, keys)
        log.info("content deleted: %s/%d images=%d", kind.target, item_id, len(keys))
        if was_public:
            request_rebuild(f"{kind.target}/{item_id} deleted")


for _kind in KINDS.values():
    register(_kind)


def counts(db: Session) -> dict[str, int]:  # 테스트·디버깅용
    return {t: db.scalar(select(func.count()).select_from(k.model)) or 0 for t, k in KINDS.items()}
