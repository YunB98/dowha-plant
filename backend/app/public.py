"""손님용 조회 API (docs/api-spec.md 1장). 인증 없음, 공개된 것만 보여 준다.

- 비공개(hidden, draft, is_published=false)는 목록에서 빠지고 상세는 404 (존재 여부도 숨긴다)
- 사진은 s3_key 대신 CloudFront 주소 image_url로 준다 (media 버킷 images/ → /images/*)
- 대표 사진(thumbnail_url)은 sort_order가 가장 작은 사진
- 사진은 항목마다 따로 읽지 않고 한 번에 읽는다 (N+1 방지)
"""

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.config import get_settings
from app.db import get_db
from app.models import ORGANIZATION_TYPES, Case, Image, PlantGuide, Setting, ShowcaseItem, Workshop

router = APIRouter(prefix="/api/v1", tags=["public"])

OrganizationType = Literal[ORGANIZATION_TYPES]  # type: ignore[valid-type]


# ---------- 응답 형식 ----------


class ImageOut(BaseModel):
    id: int
    image_url: str
    alt_text: str


class WorkshopSummary(BaseModel):
    id: int
    name: str
    price_per_person: int
    min_people: int
    max_people: int
    duration_min: int
    duration_max: int
    is_seasonal: bool
    supports_outreach: bool
    status: str
    thumbnail_url: str | None


class WorkshopDetail(WorkshopSummary):
    description: str
    images: list[ImageOut]


class WorkshopRef(BaseModel):
    id: int
    name: str


class CaseSummary(BaseModel):
    id: int
    title: str
    organization_type: str
    organization_display_name: str
    held_on: date
    participant_count: int | None
    audience: str | None
    workshop: WorkshopRef | None
    thumbnail_url: str | None


class CaseDetail(CaseSummary):
    summary: str
    images: list[ImageOut]


class CasePage(BaseModel):
    items: list[CaseSummary]
    total: int
    page: int
    size: int


class ShowcaseOut(BaseModel):
    id: int
    title: str
    description: str
    store_url: str | None
    images: list[ImageOut]


class GuideSummary(BaseModel):
    slug: str
    name: str
    difficulty: str
    summary: str
    thumbnail_url: str | None


class GuideDetail(GuideSummary):
    scientific_name: str | None
    light: str
    watering: str
    temperature: str
    humidity: str
    seasonal_care: str
    troubleshooting: str
    images: list[ImageOut]


# ---------- 공통 ----------


def public_url(key: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/{key.lstrip('/')}"


def images_by_owner(db: Session, owner: InstrumentedAttribute[int | None], ids: list[int]) -> dict[int, list[ImageOut]]:
    """owner(예: Image.workshop_id)가 ids 중 하나인 사진을 sort_order 순으로 묶어 돌려준다."""
    result: dict[int, list[ImageOut]] = {i: [] for i in ids}
    if not ids:
        return result
    rows = db.execute(
        select(owner, Image.id, Image.s3_key, Image.alt_text)
        .where(owner.in_(ids))
        .order_by(owner, Image.sort_order, Image.id)
    )
    for owner_id, image_id, key, alt in rows:
        result[owner_id].append(ImageOut(id=image_id, image_url=public_url(key), alt_text=alt))
    return result


def thumbnail(images: list[ImageOut]) -> str | None:
    return images[0].image_url if images else None


def not_found() -> HTTPException:
    return HTTPException(status_code=404)


# ---------- 가게 정보 ----------

# 공개해도 되는 설정 키 → 응답 위치. privacy.* 같은 내부 값은 내보내지 않는다.
STORE_KEYS: dict[str, tuple[str, str]] = {
    "contact.phone": ("contact", "phone"),
    "contact.kakao_url": ("contact", "kakao_url"),
    "contact.instagram": ("contact", "instagram"),
    "links.smartstore_url": ("links", "smartstore_url"),
    "links.naver_place_url": ("links", "naver_place_url"),
    "store.address": ("store", "address"),
    "store.hours": ("store", "hours"),
    "outreach.service_area": ("outreach", "service_area"),
}


@router.get("/store")
def store(db: Session = Depends(get_db)) -> dict[str, dict[str, Any]]:
    """아직 채우지 않은 값은 null (화면에서 그 항목을 숨긴다)."""
    body: dict[str, dict[str, Any]] = {}
    for group, field in STORE_KEYS.values():
        body.setdefault(group, {})[field] = None
    body["outreach"]["brochure_url"] = None

    keys = [*STORE_KEYS, "outreach.brochure_s3_key"]
    for key, value in db.execute(select(Setting.key, Setting.value).where(Setting.key.in_(keys))):
        if key == "outreach.brochure_s3_key":
            body["outreach"]["brochure_url"] = public_url(value) if value else None
        else:
            group, field = STORE_KEYS[key]
            body[group][field] = value
    return body


# ---------- 클래스 ----------

VISIBLE_WORKSHOP = Workshop.status.in_(("open", "closed"))


def _workshop_fields(w: Workshop) -> dict[str, Any]:
    return {f: getattr(w, f) for f in WorkshopSummary.model_fields if f != "thumbnail_url"}


@router.get("/workshops")
def workshops(db: Session = Depends(get_db)) -> list[WorkshopSummary]:
    rows = db.scalars(select(Workshop).where(VISIBLE_WORKSHOP).order_by(Workshop.sort_order, Workshop.id)).all()
    images = images_by_owner(db, Image.workshop_id, [w.id for w in rows])
    return [WorkshopSummary(**_workshop_fields(w), thumbnail_url=thumbnail(images[w.id])) for w in rows]


@router.get("/workshops/{workshop_id}")
def workshop(workshop_id: int, db: Session = Depends(get_db)) -> WorkshopDetail:
    w = db.scalar(select(Workshop).where(Workshop.id == workshop_id, VISIBLE_WORKSHOP))
    if w is None:
        raise not_found()
    images = images_by_owner(db, Image.workshop_id, [w.id])[w.id]
    return WorkshopDetail(
        **_workshop_fields(w), description=w.description, thumbnail_url=thumbnail(images), images=images
    )


# ---------- 진행 사례 ----------


def _case_fields(c: Case, workshop_name: str | None, images: list[ImageOut]) -> dict[str, Any]:
    return {
        "id": c.id,
        "title": c.title,
        "organization_type": c.organization_type,
        "organization_display_name": c.organization_display_name,
        "held_on": c.held_on,
        "participant_count": c.participant_count,
        "audience": c.audience,
        # 숨긴 클래스는 이름도 보여 주지 않는다
        "workshop": WorkshopRef(id=c.workshop_id, name=workshop_name) if workshop_name else None,
        "thumbnail_url": thumbnail(images),
    }


def _case_query():  # noqa: ANN202
    return select(Case, Workshop.name).outerjoin(Workshop, (Case.workshop_id == Workshop.id) & VISIBLE_WORKSHOP)


@router.get("/cases")
def cases(
    organization_type: OrganizationType | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> CasePage:
    where = [Case.is_published.is_(True)]
    if organization_type:
        where.append(Case.organization_type == organization_type)

    total = db.scalar(select(func.count()).select_from(Case).where(*where)) or 0
    rows = db.execute(
        _case_query().where(*where).order_by(Case.held_on.desc(), Case.id.desc()).limit(size).offset((page - 1) * size)
    ).all()
    images = images_by_owner(db, Image.case_id, [c.id for c, _ in rows])
    items = [CaseSummary(**_case_fields(c, name, images[c.id])) for c, name in rows]
    return CasePage(items=items, total=total, page=page, size=size)


@router.get("/cases/{case_id}")
def case(case_id: int, db: Session = Depends(get_db)) -> CaseDetail:
    row = db.execute(_case_query().where(Case.id == case_id, Case.is_published.is_(True))).one_or_none()
    if row is None:
        raise not_found()
    c, name = row
    images = images_by_owner(db, Image.case_id, [c.id])[c.id]
    return CaseDetail(**_case_fields(c, name, images), summary=c.summary, images=images)


# ---------- 작품 갤러리 ----------


@router.get("/showcase")
def showcase(db: Session = Depends(get_db)) -> list[ShowcaseOut]:
    rows = db.scalars(
        select(ShowcaseItem)
        .where(ShowcaseItem.is_published.is_(True))
        .order_by(ShowcaseItem.sort_order, ShowcaseItem.id)
    ).all()
    images = images_by_owner(db, Image.showcase_item_id, [s.id for s in rows])
    return [
        ShowcaseOut(id=s.id, title=s.title, description=s.description, store_url=s.store_url, images=images[s.id])
        for s in rows
    ]


# ---------- 식물 가이드 ----------

PUBLISHED_GUIDE = PlantGuide.status == "published"


@router.get("/guides")
def guides(db: Session = Depends(get_db)) -> list[GuideSummary]:
    rows = db.scalars(select(PlantGuide).where(PUBLISHED_GUIDE).order_by(PlantGuide.name, PlantGuide.id)).all()
    images = images_by_owner(db, Image.plant_guide_id, [g.id for g in rows])
    return [
        GuideSummary(
            slug=g.slug, name=g.name, difficulty=g.difficulty, summary=g.summary, thumbnail_url=thumbnail(images[g.id])
        )
        for g in rows
    ]


@router.get("/guides/{slug}")
def guide(slug: str, db: Session = Depends(get_db)) -> GuideDetail:
    g = db.scalar(select(PlantGuide).where(PlantGuide.slug == slug, PUBLISHED_GUIDE))
    if g is None:
        raise not_found()
    images = images_by_owner(db, Image.plant_guide_id, [g.id])[g.id]
    fields = {f: getattr(g, f) for f in GuideDetail.model_fields if f not in ("thumbnail_url", "images")}
    return GuideDetail(**fields, thumbnail_url=thumbnail(images), images=images)
