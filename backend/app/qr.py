"""QR 간접 연결 GET /q/{code} (ADR 0013, docs/api-spec.md "QR 연결").

인쇄된 카드에는 /q/{code}만 들어 있다. 가이드가 바뀌거나 사라져도 카드는 깨지지 않고,
여기서 스캔 수를 센다.

- 응답은 JSON이 아니라 302. 손님 휴대폰 브라우저가 바로 따라간다
- Location은 상대 주소. 이 서버는 origin.dowha-plant.shop 이름으로 요청을 받으므로
  절대 주소를 만들면 손님이 오리진으로 가 버린다
- Cache-Control: no-store (CloudFront가 캐시하면 스캔이 기록되지 않는다)
- 스캔 기록이 실패해도 리디렉션은 반드시 한다
- 사이트는 trailingSlash: true로 빌드되므로 끝에 /를 붙여 리디렉션을 한 번 줄인다
"""

import logging
import re
from urllib.parse import urlencode

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.metrics import QR_SCAN_FAILED, QR_SCANS
from app.models import PlantGuide, QrCode, QrScan

router = APIRouter(tags=["qr"])
log = logging.getLogger("dowha.qr")

GUIDES = "/guides/"
CODE_RE = re.compile(r"^[2-9A-HJKMNP-Z]{6,8}$")  # 모델 CHECK와 같은 규칙


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=302, headers={"Cache-Control": "no-store"})


def _with_utm(path: str, code: str) -> str:
    return path + "?" + urlencode({"utm_source": "qr", "utm_medium": "card", "utm_campaign": code})


@router.get("/q/{code}", include_in_schema=True, response_class=RedirectResponse, status_code=302)
def scan(code: str, db: Session = Depends(get_db)) -> RedirectResponse:
    code = code.strip().upper()  # 대소문자 구분 없음
    if not CODE_RE.fullmatch(code):
        QR_SCANS.labels(result="unknown").inc()
        return _redirect(GUIDES)

    try:
        row = db.execute(
            select(QrCode.id, QrCode.is_active, PlantGuide.slug, PlantGuide.status)
            .outerjoin(PlantGuide, QrCode.plant_guide_id == PlantGuide.id)
            .where(QrCode.code == code)
        ).one_or_none()
    except SQLAlchemyError:
        # DB가 안 되면 기록 없이 가이드 목록으로 (가이드 페이지는 S3 정적 파일이라 열린다)
        log.exception("qr lookup failed")
        QR_SCAN_FAILED.inc()
        return _redirect(_with_utm(GUIDES, code))

    if row is None:
        QR_SCANS.labels(result="unknown").inc()
        return _redirect(GUIDES)

    qr_id, is_active, slug, guide_status = row
    if is_active and slug and guide_status == "published":
        result, target = "guide", f"{GUIDES}{slug}/"
    else:
        result, target = "fallback", GUIDES

    try:
        db.add(QrScan(qr_code_id=qr_id))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.exception("qr scan record failed: code=%s", code)
        QR_SCAN_FAILED.inc()

    QR_SCANS.labels(result=result).inc()
    return _redirect(_with_utm(target, code))
