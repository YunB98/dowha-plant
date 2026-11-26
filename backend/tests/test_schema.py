"""DB 제약이 설계(docs/db-schema.md)대로 동작하는지 확인한다.

애플리케이션 검증과 별개로, 잘못된 데이터는 DB가 마지막으로 막아야 한다.
"""

from datetime import UTC, date, datetime

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Base, Case, Image, Inquiry, PlantGuide, QrCode, QrScan, Setting, Workshop
from tests.conftest import alembic_config


def test_models_match_migrations() -> None:
    """모델을 바꾸고 마이그레이션을 안 만들면 실패한다 (alembic check와 같음)."""
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_downgrade_and_upgrade_round_trip() -> None:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_seed_data(db: Session) -> None:
    names = db.scalars(select(Workshop.name).order_by(Workshop.sort_order)).all()
    assert names == ["화분 꾸미기 & 가드닝", "수형 잡기", "크리스마스 생화 리스"]
    assert db.get(Setting, "privacy.retention_months").value == 6


def _expect_violation(db: Session, obj: object, constraint: str) -> None:
    db.add(obj)
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    assert constraint in str(exc.value)
    db.rollback()


def test_workshop_status_check(db: Session) -> None:
    _expect_violation(db, Workshop(name="x", price_per_person=1, status="draft"), "ck_workshops_status")


def test_workshop_people_range(db: Session) -> None:
    _expect_violation(
        db, Workshop(name="x", price_per_person=1, min_people=5, max_people=4), "ck_workshops_people_range"
    )


def test_image_needs_exactly_one_owner(db: Session) -> None:
    guide = PlantGuide(slug="monstera", name="몬스테라")
    workshop = Workshop(name="x", price_per_person=1)
    db.add_all([guide, workshop])
    db.flush()

    db.add(Image(plant_guide_id=guide.id, s3_key="images/guides/1/a.jpg"))
    db.flush()  # 하나면 통과

    _expect_violation(db, Image(s3_key="images/none.jpg"), "ck_images_exactly_one_owner")


def test_image_two_owners_rejected(db: Session) -> None:
    guide = PlantGuide(slug="pothos", name="스킨답서스")
    workshop = Workshop(name="x", price_per_person=1)
    db.add_all([guide, workshop])
    db.flush()
    _expect_violation(
        db,
        Image(plant_guide_id=guide.id, workshop_id=workshop.id, s3_key="images/x.jpg"),
        "ck_images_exactly_one_owner",
    )


@pytest.mark.parametrize("slug", ["Monstera", "monstera_deliciosa", "-monstera", "몬스테라"])
def test_guide_slug_format(db: Session, slug: str) -> None:
    _expect_violation(db, PlantGuide(slug=slug, name="x"), "ck_plant_guides_slug_format")


@pytest.mark.parametrize("code", ["ABC12O", "ABCDE", "abcdef", "ABCD1I"])
def test_qr_code_format(db: Session, code: str) -> None:
    # 0, O, 1, I, L 같은 헷갈리는 문자, 소문자, 5자 이하는 거부
    _expect_violation(db, QrCode(code=code), "ck_qr_codes_code_format")


def test_qr_code_valid_and_unique(db: Session) -> None:
    db.add(QrCode(code="K7MP2Q"))
    db.flush()
    _expect_violation(db, QrCode(code="K7MP2Q"), "uq_qr_codes_code")


def test_qr_code_with_scans_cannot_be_deleted(db: Session) -> None:
    """인쇄된 카드가 있으므로 스캔 기록이 있는 QR 코드는 지울 수 없다 (ADR 0013)."""
    qr = QrCode(code="H8RT4W")
    db.add(qr)
    db.flush()
    db.add(QrScan(qr_code_id=qr.id))
    db.flush()
    db.delete(qr)
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    assert "fk_qr_scans_qr_code_id_qr_codes" in str(exc.value)


def test_deleting_guide_keeps_qr_code(db: Session) -> None:
    guide = PlantGuide(slug="calathea", name="칼라테아")
    db.add(guide)
    db.flush()
    qr = QrCode(code="T3VX9N", plant_guide_id=guide.id)
    db.add(qr)
    db.flush()

    db.delete(guide)
    db.flush()
    db.refresh(qr)
    assert qr.plant_guide_id is None  # SET NULL: QR은 남고 가이드 목록으로 안내된다


def _inquiry(**kw: object) -> Inquiry:
    base = dict(type="outreach", contact_name="홍길동", phone="010-0000-0000", privacy_agreed_at=datetime.now(UTC))
    base.update(kw)
    return Inquiry(**base)


def test_inquiry_requires_contact_until_purged(db: Session) -> None:
    _expect_violation(db, _inquiry(phone=None), "ck_inquiries_contact_required")

    db.add(_inquiry(phone=None, contact_name="(삭제됨)", pii_purged_at=datetime.now(UTC)))
    db.flush()  # 개인정보 삭제 후에는 연락처가 없어도 된다


def test_inquiry_enum_checks(db: Session) -> None:
    _expect_violation(db, _inquiry(type="order"), "ck_inquiries_type")
    _expect_violation(db, _inquiry(source="facebook"), "ck_inquiries_source")


def test_case_keeps_when_workshop_deleted(db: Session) -> None:
    workshop = Workshop(name="x", price_per_person=1)
    db.add(workshop)
    db.flush()
    case = Case(
        workshop_id=workshop.id,
        title="초등학생 20명과 다육 화분 만들기",
        organization_type="school",
        organization_display_name="전주 ○○초등학교",
        held_on=date(2026, 11, 1),
    )
    db.add(case)
    db.flush()
    db.delete(workshop)
    db.flush()
    db.refresh(case)
    assert case.workshop_id is None
