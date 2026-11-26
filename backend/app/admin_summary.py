"""관리 화면 첫 페이지 요약 (docs/api-spec.md 2장 "요약").

"이번 달"은 한국 시간 기준 1일 0시부터. 한국은 서머타임이 없어 UTC+9 고정으로 계산한다
(slim 이미지에 시간대 데이터베이스가 없어도 된다).
"""

from datetime import UTC, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import current_admin
from app.db import get_db
from app.models import Case, Inquiry, PlantGuide, QrScan, ShowcaseItem

router = APIRouter(prefix="/api/v1/admin", tags=["admin-summary"], dependencies=[Depends(current_admin)])

KST = timezone(timedelta(hours=9))


class InquiryCounts(BaseModel):
    received: int  # 아직 연락하지 않은 문의 (가장 먼저 봐야 할 숫자)
    contacted: int
    this_month: int


class QrCounts(BaseModel):
    last_30_days: int


class ContentCounts(BaseModel):
    cases: int  # 공개된 것만 (손님이 보는 숫자)
    guides_published: int
    showcase: int


class Summary(BaseModel):
    inquiries: InquiryCounts
    qr_scans: QrCounts
    content: ContentCounts


def month_start_kst(now: datetime) -> datetime:
    local = now.astimezone(KST)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> Summary:
    now = datetime.now(UTC)
    status_counts = dict(
        db.execute(
            select(Inquiry.status, func.count())
            .where(Inquiry.status.in_(("received", "contacted")))
            .group_by(Inquiry.status)
        ).all()
    )

    def count(model: type, *where: object) -> int:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    return Summary(
        inquiries=InquiryCounts(
            received=status_counts.get("received", 0),
            contacted=status_counts.get("contacted", 0),
            this_month=count(Inquiry, Inquiry.created_at >= month_start_kst(now)),
        ),
        qr_scans=QrCounts(last_30_days=count(QrScan, QrScan.scanned_at >= now - timedelta(days=30))),
        content=ContentCounts(
            cases=count(Case, Case.is_published.is_(True)),
            guides_published=count(PlantGuide, PlantGuide.status == "published"),
            showcase=count(ShowcaseItem, ShowcaseItem.is_published.is_(True)),
        ),
    )
