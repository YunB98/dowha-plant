"""처리 끝난 문의의 개인정보 자동 삭제와 미삭제 경보 지표."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import purge
from app.models import Inquiry, Setting

NOW = datetime(2026, 12, 1, 3, 30, tzinfo=UTC)


def make(db: Session, status: str = "completed", completed_at: datetime | None = None, **kw: object) -> Inquiry:
    fields: dict[str, object] = {
        "type": "outreach", "status": status, "organization_name": "전주 ○○초", "organization_type": "school",
        "contact_name": "김담당", "phone": "010-1234-5678", "email": "kim@example.com", "people_count": 20,
        "location": "전주", "source": "search", "utm_source": "naver", "message": "010-9999-8888로도 연락 주세요",
        "admin_memo": "김 선생님 휴대폰 따로 받음", "privacy_agreed_at": NOW - timedelta(days=400),
        "completed_at": completed_at,
    }
    fields.update(kw)
    inquiry = Inquiry(**fields)
    db.add(inquiry)
    db.flush()
    return inquiry


@pytest.fixture(autouse=True)
def clean(db: Session) -> None:
    db.execute(delete(Inquiry))


def months_ago(n: int, days: int = 0) -> datetime:
    """NOW(2026-12-01)에서 n개월 전 1일, 거기서 days일 더 전."""
    year, month = divmod(2026 * 12 + 12 - 1 - n, 12)
    return datetime(year, month + 1, 1, 3, 30, tzinfo=UTC) - timedelta(days=days)


def test_purges_closed_and_expired(db: Session) -> None:
    done = make(db, "completed", months_ago(6, days=1))
    canceled = make(db, "canceled", months_ago(7))
    assert sorted(purge.purge(db, NOW)) == sorted([done.id, canceled.id])

    db.refresh(done)
    assert (done.contact_name, done.phone, done.email, done.message, done.admin_memo) == (None, None, None, "", "")
    assert done.pii_purged_at == NOW
    # 통계에 필요한 값은 남긴다
    assert (done.type, done.status, done.organization_name, done.people_count, done.source, done.utm_source) == (
        "outreach", "completed", "전주 ○○초", 20, "search", "naver"
    )


@pytest.mark.parametrize(
    ("status", "completed_at", "kw"),
    [
        ("completed", months_ago(6, days=-1), {}),  # 기한까지 하루 남음
        ("confirmed", None, {}),  # 진행 중 (오래됐어도)
        ("received", None, {"created_at": NOW - timedelta(days=900)}),
        ("completed", months_ago(12), {"pii_purged_at": months_ago(5), "contact_name": None, "phone": None, "email": None}),
    ],
    ids=["not-yet", "in-progress", "old-received", "already-purged"],
)
def test_keeps(db: Session, status: str, completed_at: datetime | None, kw: dict) -> None:
    inquiry = make(db, status, completed_at, **kw)
    before = inquiry.pii_purged_at
    assert purge.purge(db, NOW) == []
    db.refresh(inquiry)
    assert inquiry.pii_purged_at == before


def test_month_arithmetic_end_of_month(db: Session) -> None:
    """5월 31일 완료 + 6개월 → 11월 30일 지나야 삭제 (11월 31일은 없다)."""
    inquiry = make(db, "completed", datetime(2026, 5, 31, 12, tzinfo=UTC))
    assert purge.purge(db, datetime(2026, 11, 30, 11, tzinfo=UTC)) == []
    assert purge.purge(db, datetime(2026, 12, 1, 0, tzinfo=UTC)) == [inquiry.id]


def test_retention_setting(db: Session) -> None:
    inquiry = make(db, "completed", months_ago(4))
    assert purge.purge(db, NOW) == []  # 기본 6개월
    db.merge(Setting(key="privacy.retention_months", value=3))
    db.flush()
    assert purge.purge(db, NOW) == [inquiry.id]


@pytest.mark.parametrize("value", [0, 61, "6", True, None, {"months": 6}])
def test_bad_retention_falls_back_to_default(db: Session, value: object) -> None:
    if value is None:
        db.execute(delete(Setting).where(Setting.key == "privacy.retention_months"))
    else:
        db.merge(Setting(key="privacy.retention_months", value=value))
    db.flush()
    assert purge.retention_months(db) == 6


def test_reopened_inquiry_is_not_purged(admin_client: TestClient, db: Session) -> None:
    """끝난 문의를 다시 진행 중으로 돌리면 completed_at이 지워져 대상에서 빠진다."""
    inquiry = make(db, "completed", months_ago(8))
    assert admin_client.patch(f"/api/v1/admin/inquiries/{inquiry.id}", json={"status": "contacted"}).status_code == 200
    assert purge.purge(db, NOW) == []


def test_admin_sees_purged(admin_client: TestClient, db: Session) -> None:
    inquiry = make(db, "completed", months_ago(8))
    purge.purge(db, NOW)
    body = admin_client.get(f"/api/v1/admin/inquiries/{inquiry.id}").json()
    assert body["contact_name"] is None and body["phone"] is None and body["message"] == ""
    listed = admin_client.get("/api/v1/admin/inquiries").json()["items"][0]
    assert listed["pii_purged"] is True and listed["phone"] is None


# ---------- 실행 명령 ----------


@contextmanager
def same_session(db: Session):  # 테스트 트랜잭션을 그대로 쓰고 닫지 않는다
    yield db


def test_cli_dry_run_then_purge(db: Session, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    inquiry = make(db, "completed", datetime.now(UTC) - timedelta(days=400))
    factory = lambda: same_session(db)  # noqa: E731

    assert purge.main(["--dry-run"], session_factory=factory) == 0
    assert "삭제 대상 1건 (보관 6개월)" in capsys.readouterr().out
    db.refresh(inquiry)
    assert inquiry.pii_purged_at is None  # dry-run은 지우지 않는다

    assert purge.main([], session_factory=factory) == 0
    assert "개인정보 삭제 1건" in capsys.readouterr().out
    db.refresh(inquiry)
    assert inquiry.pii_purged_at is not None


def test_purge_log_has_no_personal_data(db: Session, caplog: pytest.LogCaptureFixture) -> None:
    make(db, "completed", months_ago(8))
    with caplog.at_level("INFO", logger="dowha.purge"):
        purge.purge(db, NOW)
    assert "pii purge: 1 inquiries" in caplog.text
    assert "김담당" not in caplog.text and "010-1234-5678" not in caplog.text


# ---------- 미삭제 경보 지표 ----------


def metric_value(collector: purge.OverdueCollector) -> float | None:
    families = list(collector.collect())
    return families[0].samples[0].value if families else None


def test_overdue_metric_counts_after_grace(db: Session) -> None:
    collector = purge.OverdueCollector(lambda: same_session(db))
    now = datetime.now(UTC)
    make(db, "completed", now - timedelta(days=200))  # 6개월 + 2일 넘음 → 밀림
    make(db, "completed", now - timedelta(days=183))  # 막 기한이 지남, 오늘 밤 타이머가 지울 것 → 아직 경보 아님
    make(db, "completed", now - timedelta(days=30))
    assert metric_value(collector) == 1

    purge.purge(db)
    assert metric_value(collector) == 0


def test_overdue_metric_skips_on_db_error() -> None:
    @contextmanager
    def broken():
        raise OperationalError("SELECT", {}, Exception("db down"))
        yield

    assert metric_value(purge.OverdueCollector(broken)) is None


def test_metrics_endpoint_exposes_overdue(client: TestClient) -> None:
    assert "dowha_inquiries_pii_overdue" in client.get("/metrics/").text
