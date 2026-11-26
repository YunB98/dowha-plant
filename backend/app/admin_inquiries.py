"""사장님 문의 관리 (docs/api-spec.md 2장 "문의"). 모든 요청은 로그인 필요.

상태 흐름: received → contacted → quoted → confirmed → completed (어디서든 canceled)
사장님이 상황에 맞게 고르도록 순서를 강제하지는 않는다. 서버는 시각만 기록한다.
- contacted_at: 처음으로 연락한 뒤 상태(contacted 이후)가 됐을 때 한 번
- completed_at: completed·canceled가 됐을 때. 개인정보 보관 기간은 이 시각부터 센다.
  다시 진행 중 상태로 돌리면 지운다 (진행 중인 문의의 연락처가 지워지면 안 된다)

개인정보
- 목록은 연락처 가운데를 가린다. 전체 연락처는 상세에서만 보이고, 상세 조회는 로그에 남긴다(누가 몇 번 문의를)
- 개인정보를 지운 문의(pii_purged_at)는 해당 필드가 null이고, 진행 중 상태로 되돌릴 수 없다
"""

import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import current_admin
from app.db import get_db
from app.models import AdminUser, Inquiry, Workshop

router = APIRouter(prefix="/api/v1/admin/inquiries", tags=["admin-inquiries"])
log = logging.getLogger("dowha.admin")

Status = Literal["received", "contacted", "quoted", "confirmed", "completed", "canceled"]
InquiryType = Literal["outreach", "group_visit", "corporate_order", "other"]
assert set(Status.__args__) == set(Inquiry.STATUSES)
assert set(InquiryType.__args__) == set(Inquiry.TYPES)

AFTER_CONTACT = {"contacted", "quoted", "confirmed", "completed"}
CLOSED = {"completed", "canceled"}


# ---------- 가리기 ----------


def mask_phone(phone: str | None) -> str | None:
    """010-1234-5678 → 010-****-5678, 02-123-4567 → 02-***-4567"""
    if not phone:
        return phone
    parts = phone.split("-")
    if len(parts) != 3:
        return "*" * max(len(phone) - 4, 0) + phone[-4:]
    return f"{parts[0]}-{'*' * len(parts[1])}-{parts[2]}"


def mask_email(email: str | None) -> str | None:
    """dowha.shop@example.com → do***@example.com"""
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    return f"{local[:2]}***@{domain}"


# ---------- 응답 형식 ----------


class WorkshopRef(BaseModel):
    id: int
    name: str


class InquiryListItem(BaseModel):
    id: int
    type: str
    status: str
    organization_name: str | None
    contact_name: str | None
    phone: str | None  # 가린 값
    email: str | None  # 가린 값
    people_count: int | None
    preferred_schedule: str | None
    workshop: WorkshopRef | None
    source: str | None
    created_at: datetime
    pii_purged: bool


class InquiryPage(BaseModel):
    items: list[InquiryListItem]
    total: int
    page: int
    size: int


class InquiryDetail(BaseModel):
    id: int
    type: str
    status: str
    organization_name: str | None
    organization_type: str | None
    contact_name: str | None
    phone: str | None
    email: str | None
    people_count: int | None
    audience: str | None
    preferred_schedule: str | None
    location: str | None
    workshop: WorkshopRef | None
    budget_range: str | None
    source: str | None
    landing_referrer: str | None
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    message: str
    admin_memo: str
    privacy_agreed_at: datetime
    contacted_at: datetime | None
    completed_at: datetime | None
    pii_purged_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InquiryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status | None = None
    admin_memo: str | None = Field(None, max_length=2000)

    @model_validator(mode="after")
    def _not_empty(self) -> "InquiryUpdate":
        if self.status is None and self.admin_memo is None:
            raise ValueError("바꿀 항목(status, admin_memo)을 보내주세요.")
        return self


# ---------- 공통 ----------


def _workshop(inquiry: Inquiry, name: str | None) -> WorkshopRef | None:
    return WorkshopRef(id=inquiry.workshop_id, name=name) if inquiry.workshop_id and name else None


def _detail(inquiry: Inquiry, workshop_name: str | None) -> InquiryDetail:
    fields = {f: getattr(inquiry, f) for f in InquiryDetail.model_fields if f != "workshop"}
    return InquiryDetail(**fields, workshop=_workshop(inquiry, workshop_name))


def _get(db: Session, inquiry_id: int) -> tuple[Inquiry, str | None]:
    row = db.execute(
        select(Inquiry, Workshop.name)
        .outerjoin(Workshop, Inquiry.workshop_id == Workshop.id)
        .where(Inquiry.id == inquiry_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404)
    return row[0], row[1]


def apply_status(inquiry: Inquiry, new: str, now: datetime) -> None:
    """상태를 바꾸고 시각을 기록한다. 같은 상태로 바꾸면 아무것도 하지 않는다."""
    if new == inquiry.status:
        return
    if inquiry.pii_purged_at is not None and new not in CLOSED:
        raise HTTPException(status_code=409, detail="개인정보를 지운 문의는 진행 중 상태로 되돌릴 수 없어요.")
    if new in AFTER_CONTACT and inquiry.contacted_at is None:
        inquiry.contacted_at = now
    if new in CLOSED and inquiry.status not in CLOSED:
        inquiry.completed_at = now
    elif new not in CLOSED:
        inquiry.completed_at = None
    inquiry.status = new


# ---------- API ----------


@router.get("")
def list_inquiries(
    status: Status | None = None,
    type: InquiryType | None = None,  # noqa: A002  (명세의 쿼리 이름)
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(current_admin),
) -> InquiryPage:
    where = []
    if status:
        where.append(Inquiry.status == status)
    if type:
        where.append(Inquiry.type == type)

    total = db.scalar(select(func.count()).select_from(Inquiry).where(*where)) or 0
    rows = db.execute(
        select(Inquiry, Workshop.name)
        .outerjoin(Workshop, Inquiry.workshop_id == Workshop.id)
        .where(*where)
        .order_by(Inquiry.created_at.desc(), Inquiry.id.desc())
        .limit(size)
        .offset((page - 1) * size)
    ).all()
    items = [
        InquiryListItem(
            id=i.id,
            type=i.type,
            status=i.status,
            organization_name=i.organization_name,
            contact_name=i.contact_name,
            phone=mask_phone(i.phone),
            email=mask_email(i.email),
            people_count=i.people_count,
            preferred_schedule=i.preferred_schedule,
            workshop=_workshop(i, name),
            source=i.source,
            created_at=i.created_at,
            pii_purged=i.pii_purged_at is not None,
        )
        for i, name in rows
    ]
    return InquiryPage(items=items, total=total, page=page, size=size)


@router.get("/{inquiry_id}")
def get_inquiry(
    inquiry_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(current_admin)
) -> InquiryDetail:
    inquiry, name = _get(db, inquiry_id)
    log.info("inquiry viewed: admin=%s inquiry=%d", admin.username, inquiry.id)
    return _detail(inquiry, name)


@router.patch("/{inquiry_id}")
def update_inquiry(
    inquiry_id: int,
    body: InquiryUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(current_admin),
) -> InquiryDetail:
    inquiry, name = _get(db, inquiry_id)
    before = inquiry.status
    if body.status is not None:
        apply_status(inquiry, body.status, datetime.now(UTC))
    if body.admin_memo is not None:
        inquiry.admin_memo = body.admin_memo.strip()
    db.commit()
    db.refresh(inquiry)
    log.info("inquiry updated: admin=%s inquiry=%d status=%s->%s", admin.username, inquiry.id, before, inquiry.status)
    return _detail(inquiry, name)
