"""출강·단체 견적 문의 접수 (docs/api-spec.md "문의 접수").

요청 수 제한(IP당 10분에 5회 수준)은 Nginx가 한다 (deploy/nginx, api-spec 4장).
"""

import re
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.db import get_db
from app.metrics import INQUIRIES_CREATED, INQUIRIES_SPAM
from app.models import AUDIENCES, ORGANIZATION_TYPES, Inquiry, Workshop
from app.notify import inquiry_message, send_telegram

router = APIRouter(prefix="/api/v1", tags=["inquiries"])

InquiryType = Literal["outreach", "group_visit", "corporate_order", "other"]
OrganizationType = Literal["school", "kindergarten", "welfare", "public", "company", "other"]
Audience = Literal["children", "teens", "adults", "seniors", "mixed"]
Source = Literal["search", "instagram", "qr", "referral", "returning", "other"]

# 모델의 CHECK 값과 어긋나지 않게 (값을 추가할 때 한쪽만 바꾸는 실수 방지)
assert set(OrganizationType.__args__) == set(ORGANIZATION_TYPES)
assert set(Audience.__args__) == set(AUDIENCES)
assert set(InquiryType.__args__) == set(Inquiry.TYPES)
assert set(Source.__args__) == set(Inquiry.SOURCES)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_phone(value: str) -> str:
    """하이픈·공백을 허용하고 010-1234-5678 / 02-123-4567 / 063-123-4567 형식으로 맞춘다."""
    digits = re.sub(r"[\s\-().]", "", value)
    if not re.fullmatch(r"0\d{8,10}", digits):
        raise ValueError("연락처 형식이 올바르지 않아요. 예: 010-1234-5678")
    if digits.startswith("02"):
        return f"02-{digits[2:-4]}-{digits[-4:]}"
    return f"{digits[:3]}-{digits[3:-4]}-{digits[-4:]}"


class Attribution(BaseModel):
    """페이지가 첫 방문 때 sessionStorage에 저장해 둔 유입 정보"""

    model_config = ConfigDict(extra="ignore")

    landing_referrer: str | None = Field(None, max_length=500)
    utm_source: str | None = Field(None, max_length=100)
    utm_medium: str | None = Field(None, max_length=100)
    utm_campaign: str | None = Field(None, max_length=100)


class InquiryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: InquiryType
    organization_name: str = Field(min_length=1, max_length=100)
    organization_type: OrganizationType
    contact_name: str = Field(min_length=1, max_length=50)
    phone: str = Field(max_length=20)
    email: str | None = Field(None, max_length=255)
    people_count: int = Field(ge=1, le=1000)
    audience: Audience | None = None
    preferred_schedule: str = Field(min_length=1, max_length=200)
    location: str | None = Field(None, max_length=200)
    workshop_id: int | None = None
    budget_range: str | None = Field(None, max_length=50)
    source: Source
    attribution: Attribution | None = None
    message: str = Field("", max_length=1000)
    privacy_agreed: bool
    website: str | None = Field(None, description="허니팟 (화면에서 숨김). 사람은 비워 둔다")

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        if not v:
            return None
        if not EMAIL_RE.fullmatch(v):
            raise ValueError("이메일 형식이 올바르지 않아요.")
        return v.lower()

    @field_validator("privacy_agreed")
    @classmethod
    def _privacy(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("개인정보 수집·이용에 동의해주세요.")
        return v

    @model_validator(mode="after")
    def _location_for_outreach(self) -> "InquiryCreate":
        if self.type == "outreach" and not self.location:
            raise ValueError("출강 문의는 수업 장소를 입력해주세요.")
        return self


class InquiryCreated(BaseModel):
    id: int | None
    type: str
    status: str
    created_at: datetime


def _field_error(field: str, message: str) -> RequestValidationError:
    return RequestValidationError(
        [{"type": "value_error", "loc": ("body", field), "msg": message, "ctx": {"error": message}}]
    )


@router.post("/inquiries", status_code=status.HTTP_201_CREATED, response_model=InquiryCreated)
def create_inquiry(
    body: InquiryCreate, background: BackgroundTasks, db: Session = Depends(get_db)
) -> InquiryCreated:
    now = datetime.now(UTC)

    # 허니팟에 값이 있으면 봇으로 보고 저장하지 않는다. 봇이 눈치채지 못하게 성공처럼 응답한다.
    if body.website:
        INQUIRIES_SPAM.inc()
        return InquiryCreated(id=None, type=body.type, status="received", created_at=now)

    if body.workshop_id is not None and db.get(Workshop, body.workshop_id) is None:
        raise _field_error("workshop_id", "선택한 클래스를 찾을 수 없어요.")

    attribution = body.attribution or Attribution()
    inquiry = Inquiry(
        type=body.type,
        organization_name=body.organization_name,
        organization_type=body.organization_type,
        contact_name=body.contact_name,
        phone=body.phone,
        email=body.email,
        people_count=body.people_count,
        audience=body.audience,
        preferred_schedule=body.preferred_schedule,
        location=body.location,
        workshop_id=body.workshop_id,
        budget_range=body.budget_range,
        source=body.source,
        landing_referrer=attribution.landing_referrer,
        utm_source=attribution.utm_source,
        utm_medium=attribution.utm_medium,
        utm_campaign=attribution.utm_campaign,
        message=body.message,
        privacy_agreed_at=now,
    )
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)

    INQUIRIES_CREATED.labels(type=inquiry.type, source=inquiry.source).inc()
    background.add_task(
        send_telegram,
        inquiry_message(
            inquiry.id, inquiry.type, body.organization_name, body.people_count,
            body.preferred_schedule, body.source,
        ),
    )
    return InquiryCreated(id=inquiry.id, type=inquiry.type, status=inquiry.status, created_at=inquiry.created_at)
