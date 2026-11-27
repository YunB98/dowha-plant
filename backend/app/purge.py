"""처리가 끝난 문의의 개인정보 자동 삭제 (docs/requirements.md, docs/db-schema.md).

대상: completed·canceled 이고 completed_at이 보관 기간(settings privacy.retention_months, 기본 6개월)보다
오래됐으며 아직 지우지 않은 문의.

지우는 것: 담당자 이름, 전화, 이메일, 요청사항(message), 사장님 메모(admin_memo).
요청사항과 메모는 자유 입력이라 개인정보가 섞여 있을 수 있어서 같이 지운다.
남기는 것: 문의 종류, 기관명·기관 종류, 인원, 일정, 장소, 유입 경로, 상태, 시각.
"홈페이지로 늘어난 출강"(confirmed·completed 수, 유입 경로) 통계는 계속 볼 수 있다.

실행: 서버의 systemd 타이머가 매일 새벽(한국 시간 03:30) 실행한다 (deploy/systemd/dowha-pii-purge.*)
    docker compose exec -T api python -m app.purge            # 지우기
    docker compose exec -T api python -m app.purge --dry-run  # 몇 건인지만 보기

감시: 실행했는지가 아니라 결과를 본다. API의 /metrics가 "기한이 지났는데 아직 남은 문의 수"
(dowha_inquiries_pii_overdue)를 내보내고, 0보다 크면 경보(PiiPurgeOverdue).
타이머가 멈췄거나 이 코드가 틀렸거나 같은 경보 하나로 잡힌다.
"""

import argparse
import logging
import sys
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime, timedelta

from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from sqlalchemy import ColumnElement, and_, func, literal, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Inquiry, Setting

log = logging.getLogger("dowha.purge")

DEFAULT_MONTHS = 6
CLOSED = ("completed", "canceled")
# 매일 한 번 도니까, 기한이 막 지난 문의는 하루 이내에 지워진다. 경보는 그 뒤부터 센다
GRACE = timedelta(days=2)


def retention_months(db: Session) -> int:
    value = db.scalar(select(Setting.value).where(Setting.key == "privacy.retention_months"))
    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 60:
        return value
    if value is not None:
        log.warning("privacy.retention_months 값이 이상해서 기본값 %d개월을 씁니다: %r", DEFAULT_MONTHS, value)
    return DEFAULT_MONTHS


def _expired(months: int, now: datetime) -> ColumnElement[bool]:
    # 개월 계산은 PostgreSQL interval에 맡긴다 (3월 31일 - 1개월 = 2월 28/29일)
    cutoff = literal(now) - func.make_interval(0, months)
    return and_(
        Inquiry.status.in_(CLOSED),
        Inquiry.completed_at.is_not(None),
        Inquiry.completed_at < cutoff,
        Inquiry.pii_purged_at.is_(None),
    )


def count_expired(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    return db.scalar(select(func.count()).select_from(Inquiry).where(_expired(retention_months(db), now))) or 0


def purge(db: Session, now: datetime | None = None) -> list[int]:
    """지운 문의 id 목록. 한 번의 UPDATE로 처리하고 커밋한다."""
    now = now or datetime.now(UTC)
    months = retention_months(db)
    ids = list(
        db.scalars(
            update(Inquiry)
            .where(_expired(months, now))
            .values(contact_name=None, phone=None, email=None, message="", admin_memo="", pii_purged_at=now)
            .returning(Inquiry.id)
        )
    )
    db.commit()
    log.info("pii purge: %d inquiries (retention %d months) ids=%s", len(ids), months, ids)
    return ids


class OverdueCollector(Collector):
    """Prometheus가 수집할 때(60초마다) DB에서 센다. 기한 + 2일이 지나도 남은 문의 수."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def describe(self) -> Iterable[GaugeMetricFamily]:
        # 등록할 때 이름만 알려 준다. 없으면 prometheus_client가 등록 순간 collect()를 불러
        # API가 시작하면서 DB를 조회하고, DB가 늦으면 시작이 멈춘다
        yield GaugeMetricFamily("dowha_inquiries_pii_overdue", "")

    def collect(self) -> Iterable[GaugeMetricFamily]:
        try:
            with self.session_factory() as db:
                overdue = count_expired(db, datetime.now(UTC) - GRACE)
        except SQLAlchemyError:
            log.warning("pii overdue count failed", exc_info=True)
            return  # DB 장애는 다른 경보(헬스 체크)가 잡는다. 값을 내보내지 않는다
        yield GaugeMetricFamily(
            "dowha_inquiries_pii_overdue", "보관 기간이 지났는데 개인정보가 남아 있는 문의 수 (0이어야 한다)", value=overdue
        )


def main(argv: Sequence[str] | None = None, session_factory: Callable[[], Session] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.purge", description="처리 끝난 문의의 개인정보 삭제")
    parser.add_argument("--dry-run", action="store_true", help="지우지 않고 대상 수만 출력")
    args = parser.parse_args(argv)
    if session_factory is None:
        from app.db import SessionLocal

        session_factory = SessionLocal

    with session_factory() as db:
        months = retention_months(db)
        if args.dry_run:
            print(f"삭제 대상 {count_expired(db)}건 (보관 {months}개월)")
            return 0
        ids = purge(db)
    print(f"개인정보 삭제 {len(ids)}건 (보관 {months}개월)")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    sys.exit(main())
