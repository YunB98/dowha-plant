"""사장님 QR 코드 관리 (docs/api-spec.md 2장 "QR 코드", ADR 0013).

- 삭제 API는 없다. 이미 인쇄된 카드가 있으므로 is_active로 끄기만 한다
- 코드는 헷갈리는 문자(0 O 1 I L)를 뺀 31글자 중 6자리 (약 8억 가지). 겹치면 다시 뽑는다
- 연결 가이드는 비공개(draft)여도 된다. 공개 전에는 스캔하면 가이드 목록으로 간다
- 인쇄 이미지는 서버에서 만든다 (segno, 순수 파이썬). QR 안에는 https://dowha-plant.shop/q/{코드}만 들어간다
  주소를 대문자로 바꾸면 QR이 더 작아지지만, CloudFront 경로(/q/*)가 대소문자를 구분해서 소문자 그대로 둔다
"""

import io
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal

import segno
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import current_admin
from app.config import get_settings
from app.db import get_db
from app.models import AdminUser, PlantGuide, QrCode, QrScan

router = APIRouter(prefix="/api/v1/admin/qr-codes", tags=["admin-qr"])
log = logging.getLogger("dowha.admin")

ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # 모델 CHECK ^[2-9A-HJKMNP-Z]{6,8}$ 와 같은 문자
CODE_LENGTH = 6


def new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def scan_url(code: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/q/{code}"


# ---------- 형식 ----------


class GuideRef(BaseModel):
    id: int
    slug: str
    name: str
    status: str


class QrOut(BaseModel):
    id: int
    code: str
    url: str
    label: str
    is_active: bool
    plant_guide: GuideRef | None
    scans_total: int
    scans_last_30_days: int
    created_at: datetime


class QrCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    plant_guide_id: int | None = None
    label: str = Field("", max_length=100)


class QrUpdate(BaseModel):
    """보낸 필드만 바꾼다. plant_guide_id: null을 보내면 연결을 끊는다 (스캔하면 가이드 목록으로)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    plant_guide_id: int | None = None
    label: str | None = Field(None, max_length=100)
    is_active: bool | None = None


# ---------- 공통 ----------


def _query():  # noqa: ANN202
    since = datetime.now(UTC) - timedelta(days=30)
    scans = (
        select(
            QrScan.qr_code_id,
            func.count().label("total"),
            func.count().filter(QrScan.scanned_at >= since).label("recent"),
        )
        .group_by(QrScan.qr_code_id)
        .subquery()
    )
    return (
        select(QrCode, PlantGuide, func.coalesce(scans.c.total, 0), func.coalesce(scans.c.recent, 0))
        .outerjoin(PlantGuide, QrCode.plant_guide_id == PlantGuide.id)
        .outerjoin(scans, scans.c.qr_code_id == QrCode.id)
    )


def _out(qr: QrCode, guide: PlantGuide | None, total: int, recent: int) -> QrOut:
    return QrOut(
        id=qr.id,
        code=qr.code,
        url=scan_url(qr.code),
        label=qr.label,
        is_active=qr.is_active,
        plant_guide=GuideRef(id=guide.id, slug=guide.slug, name=guide.name, status=guide.status) if guide else None,
        scans_total=total,
        scans_last_30_days=recent,
        created_at=qr.created_at,
    )


def _one(db: Session, qr_id: int) -> QrOut:
    row = db.execute(_query().where(QrCode.id == qr_id)).one_or_none()
    if row is None:
        raise HTTPException(status_code=404)
    return _out(*row)


def _check_guide(db: Session, guide_id: int | None) -> None:
    if guide_id is not None and db.get(PlantGuide, guide_id) is None:
        raise HTTPException(status_code=422, detail="연결할 식물 가이드가 없어요.")


# ---------- API ----------


@router.get("")
def list_qr_codes(
    plant_guide_id: int | None = None, db: Session = Depends(get_db), _: AdminUser = Depends(current_admin)
) -> list[QrOut]:
    query = _query().order_by(QrCode.created_at.desc(), QrCode.id.desc())
    if plant_guide_id is not None:
        query = query.where(QrCode.plant_guide_id == plant_guide_id)
    return [_out(*row) for row in db.execute(query).all()]


@router.post("", status_code=201)
def create_qr_code(
    body: QrCreate, db: Session = Depends(get_db), admin: AdminUser = Depends(current_admin)
) -> QrOut:
    _check_guide(db, body.plant_guide_id)
    for _ in range(5):
        qr = QrCode(code=new_code(), plant_guide_id=body.plant_guide_id, label=body.label)
        try:
            with db.begin_nested():  # 코드가 겹치면 이 부분만 되돌리고 다시 뽑는다
                db.add(qr)
        except IntegrityError:
            continue
        db.commit()
        log.info("qr created: admin=%s code=%s guide=%s", admin.username, qr.code, qr.plant_guide_id)
        return _one(db, qr.id)
    raise HTTPException(status_code=500)  # 8억 가지 중 다섯 번 연속으로 겹칠 일은 없다


@router.patch("/{qr_id}")
def update_qr_code(
    qr_id: int, body: QrUpdate, db: Session = Depends(get_db), admin: AdminUser = Depends(current_admin)
) -> QrOut:
    qr = db.get(QrCode, qr_id)
    if qr is None:
        raise HTTPException(status_code=404)
    sent = body.model_fields_set
    if "plant_guide_id" in sent:
        _check_guide(db, body.plant_guide_id)
        qr.plant_guide_id = body.plant_guide_id
    if "label" in sent and body.label is not None:
        qr.label = body.label
    if "is_active" in sent and body.is_active is not None:
        qr.is_active = body.is_active
    db.commit()
    log.info("qr updated: admin=%s code=%s fields=%s", admin.username, qr.code, ",".join(sorted(sent)))
    return _one(db, qr.id)


@router.get("/{qr_id}/image")
def qr_image(
    qr_id: int,
    format: Literal["png", "svg"] = "png",  # noqa: A002  (명세의 쿼리 이름)
    size: int = Query(10, ge=1, le=40, description="칸 하나의 픽셀 수. 10이면 약 370px"),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(current_admin),
) -> Response:
    qr = db.get(QrCode, qr_id)
    if qr is None:
        raise HTTPException(status_code=404)
    # 오류 정정 M: 카드가 조금 긁혀도 읽힌다. 테두리 4칸은 QR 규격의 최소 여백
    image = segno.make(scan_url(qr.code), error="m", boost_error=False)
    buf = io.BytesIO()
    image.save(buf, kind=format, scale=size, border=4)
    media = "image/png" if format == "png" else "image/svg+xml"
    return Response(
        buf.getvalue(),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="qr-{qr.code}.{format}"', "Cache-Control": "no-store"},
    )
