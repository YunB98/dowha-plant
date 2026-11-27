"""사장님 설정 관리 (docs/api-spec.md 2장 "설정").

- 사장님이 바꿀 수 있는 키는 손님용 /store가 보여 주는 키와 같다 (public.STORE_KEYS 하나로 관리)
- privacy.* 같은 운영 설정은 여기서 바꿀 수 없다 (알 수 없는 키로 422)
- 바꿀 키만 보낸다. null이나 빈 문자열을 보내면 값을 지운다 (손님 화면에서 그 항목이 숨는다)
- 외부 링크는 https와 정해진 주소만 받는다. 로그인이 털려도 손님을 엉뚱한 사이트로 보내기 어렵게
- 소개서 PDF 교체(PUT /admin/settings/brochure)는 S3 업로드와 함께 만든다
"""

import logging
import re
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import current_admin
from app.db import get_db
from app.inquiries import normalize_phone
from app.models import AdminUser, Setting
from app.public import STORE_KEYS, public_url

router = APIRouter(prefix="/api/v1/admin/settings", tags=["admin-settings"])
log = logging.getLogger("dowha.admin")

# 링크 키별로 허용하는 주소 (호스트가 정확히 같거나 그 하위 도메인)
LINK_HOSTS = {
    "contact.kakao_url": ("pf.kakao.com", "open.kakao.com"),
    "contact.naver_talk_url": ("naver.me", "talk.naver.com"),
    "links.smartstore_url": ("smartstore.naver.com",),
    "links.naver_place_url": ("naver.me", "map.naver.com", "m.place.naver.com", "place.naver.com"),
}
INSTAGRAM_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def _check_link(key: str, value: str) -> str:
    url = urlparse(value)
    hosts = LINK_HOSTS[key]
    host = (url.hostname or "").lower()
    if url.scheme != "https" or not any(host == h or host.endswith("." + h) for h in hosts):
        raise ValueError(f"{', '.join(hosts)} 주소(https://...)만 넣을 수 있어요.")
    return value


class SettingsUpdate(BaseModel):
    """필드 이름은 설정 키 그대로 (contact.phone 등)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    contact_phone: str | None = Field(None, alias="contact.phone", max_length=20)
    contact_kakao_url: str | None = Field(None, alias="contact.kakao_url", max_length=300)
    contact_naver_talk_url: str | None = Field(None, alias="contact.naver_talk_url", max_length=300)
    contact_instagram: str | None = Field(None, alias="contact.instagram", max_length=31)
    links_smartstore_url: str | None = Field(None, alias="links.smartstore_url", max_length=300)
    links_naver_place_url: str | None = Field(None, alias="links.naver_place_url", max_length=300)
    store_address: str | None = Field(None, alias="store.address", max_length=200)
    store_hours: str | None = Field(None, alias="store.hours", max_length=200)
    outreach_service_area: str | None = Field(None, alias="outreach.service_area", max_length=200)

    @field_validator("contact_phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return normalize_phone(v) if v else v

    @field_validator("contact_instagram")
    @classmethod
    def _instagram(cls, v: str | None) -> str | None:
        if not v:
            return v
        v = v.removeprefix("@")
        if not INSTAGRAM_RE.fullmatch(v):
            raise ValueError("인스타그램 계정 이름만 넣어주세요. 예: dowha_plantshop")
        return v

    @field_validator("contact_kakao_url", "contact_naver_talk_url", "links_smartstore_url", "links_naver_place_url")
    @classmethod
    def _link(cls, v: str | None, info: Any) -> str | None:
        if not v:
            return v
        key = cls.model_fields[info.field_name].alias
        return _check_link(key, v)


# 모델 필드와 공개 키 목록이 어긋나지 않게
assert {f.alias for f in SettingsUpdate.model_fields.values()} == set(STORE_KEYS)


def _current(db: Session) -> dict[str, Any]:
    values: dict[str, Any] = dict.fromkeys(STORE_KEYS)
    brochure = None
    for key, value in db.execute(select(Setting.key, Setting.value).where(Setting.key.in_([*STORE_KEYS, "outreach.brochure_s3_key"]))):
        if key == "outreach.brochure_s3_key":
            brochure = public_url(value) if value else None
        else:
            values[key] = value
    values["outreach.brochure_url"] = brochure  # 읽기 전용 (PUT /admin/settings/brochure로 바꾼다)
    return values


@router.get("")
def get_settings_(db: Session = Depends(get_db), _: AdminUser = Depends(current_admin)) -> dict[str, Any]:
    return _current(db)


@router.patch("")
def update_settings(
    body: SettingsUpdate, db: Session = Depends(get_db), admin: AdminUser = Depends(current_admin)
) -> dict[str, Any]:
    changes = body.model_dump(by_alias=True, exclude_unset=True)
    for key, value in changes.items():
        if value in (None, ""):
            db.execute(delete(Setting).where(Setting.key == key))
        else:
            db.merge(Setting(key=key, value=value))
    db.commit()
    log.info("settings updated: admin=%s keys=%s", admin.username, ",".join(sorted(changes)))
    return _current(db)
