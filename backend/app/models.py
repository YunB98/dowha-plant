"""DB 모델 (docs/db-schema.md).

규칙
- 상태값은 PostgreSQL ENUM 대신 VARCHAR + CHECK (값을 추가할 때 마이그레이션이 쉽다)
- 시간은 TIMESTAMPTZ, qr_scans를 뺀 모든 테이블에 created_at, updated_at
- 금액은 INTEGER(원)
- 제약 이름은 naming convention으로 고정한다 (Alembic이 이름으로 찾아 바꾸거나 지울 수 있게)
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def one_of(column: str, values: tuple[str, ...], name: str | None = None) -> CheckConstraint:
    """column이 values 중 하나인지 확인하는 CHECK. 제약 이름은 ck_<테이블>_<name>."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({quoted})", name=name or column)


# 여러 테이블이 같이 쓰는 값
ORGANIZATION_TYPES = ("school", "kindergarten", "welfare", "public", "company", "other")
AUDIENCES = ("children", "teens", "adults", "seniors", "mixed")


class Workshop(TimestampMixin, Base):
    """클래스·프로그램"""

    __tablename__ = "workshops"
    STATUSES = ("open", "closed", "hidden")

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, server_default="")
    price_per_person: Mapped[int] = mapped_column(Integer)
    min_people: Mapped[int] = mapped_column(Integer, server_default="1")
    max_people: Mapped[int] = mapped_column(Integer, server_default="4")
    duration_min: Mapped[int] = mapped_column(Integer, server_default="60")
    duration_max: Mapped[int] = mapped_column(Integer, server_default="90")
    is_seasonal: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    supports_outreach: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    status: Mapped[str] = mapped_column(String(20), server_default="open")
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")

    __table_args__ = (
        one_of("status", STATUSES),
        CheckConstraint("price_per_person >= 0", name="price_non_negative"),
        CheckConstraint("min_people >= 1 AND min_people <= max_people", name="people_range"),
        CheckConstraint("duration_min > 0 AND duration_min <= duration_max", name="duration_range"),
    )


class Case(TimestampMixin, Base):
    """출강·단체 수업 진행 사례"""

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int | None] = mapped_column(
        ForeignKey("workshops.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(100))
    organization_type: Mapped[str] = mapped_column(String(20))
    organization_display_name: Mapped[str] = mapped_column(String(100))
    held_on: Mapped[date] = mapped_column(Date)
    participant_count: Mapped[int | None] = mapped_column(Integer)
    audience: Mapped[str | None] = mapped_column(String(20))
    summary: Mapped[str] = mapped_column(Text, server_default="")
    is_published: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    __table_args__ = (
        one_of("organization_type", ORGANIZATION_TYPES),
        one_of("audience", AUDIENCES),
        Index("ix_cases_published_held_on", "is_published", text("held_on DESC")),
    )


class ShowcaseItem(TimestampMixin, Base):
    """작품 갤러리. 가격·재고는 스마트스토어가 기준"""

    __tablename__ = "showcase_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, server_default="")
    store_url: Mapped[str | None] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    is_published: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class PlantGuide(TimestampMixin, Base):
    """식물 관리 가이드. slug는 공개 후 바꾸지 않는다"""

    __tablename__ = "plant_guides"
    DIFFICULTIES = ("easy", "normal", "hard")
    STATUSES = ("draft", "published")

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    scientific_name: Mapped[str | None] = mapped_column(String(150))
    difficulty: Mapped[str] = mapped_column(String(10), server_default="normal")
    summary: Mapped[str] = mapped_column(Text, server_default="")
    light: Mapped[str] = mapped_column(Text, server_default="")
    watering: Mapped[str] = mapped_column(Text, server_default="")
    temperature: Mapped[str] = mapped_column(Text, server_default="")
    humidity: Mapped[str] = mapped_column(Text, server_default="")
    seasonal_care: Mapped[str] = mapped_column(Text, server_default="")
    troubleshooting: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        one_of("difficulty", DIFFICULTIES),
        one_of("status", STATUSES),
        # URL에 들어가므로 소문자·숫자·하이픈만
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_format"),
    )


class Image(TimestampMixin, Base):
    """사진 (공용). 4개 FK 중 정확히 하나만 값이 있다. 파일은 S3, DB에는 키만"""

    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int | None] = mapped_column(
        ForeignKey("workshops.id", ondelete="CASCADE")
    )
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    showcase_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("showcase_items.id", ondelete="CASCADE")
    )
    plant_guide_id: Mapped[int | None] = mapped_column(
        ForeignKey("plant_guides.id", ondelete="CASCADE")
    )
    s3_key: Mapped[str] = mapped_column(String(300))
    alt_text: Mapped[str] = mapped_column(String(200), server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")

    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(workshop_id, case_id, showcase_item_id, plant_guide_id) = 1",
            name="exactly_one_owner",
        ),
        # 대표 사진(sort_order 최소) 조회
        Index("ix_images_workshop_sort", "workshop_id", "sort_order"),
        Index("ix_images_case_sort", "case_id", "sort_order"),
        Index("ix_images_showcase_item_sort", "showcase_item_id", "sort_order"),
        Index("ix_images_plant_guide_sort", "plant_guide_id", "sort_order"),
    )


class QrCode(TimestampMixin, Base):
    """QR 코드. 이미 인쇄된 카드가 있으므로 행을 지우지 않는다 (ADR 0013)"""

    __tablename__ = "qr_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    plant_guide_id: Mapped[int | None] = mapped_column(
        ForeignKey("plant_guides.id", ondelete="SET NULL")
    )
    label: Mapped[str] = mapped_column(String(100), server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    __table_args__ = (
        # 헷갈리는 문자(0, O, 1, I, L)를 뺀 대문자·숫자
        CheckConstraint("code ~ '^[2-9A-HJKMNP-Z]{6,8}$'", name="code_format"),
    )


class QrScan(Base):
    """QR 스캔 기록. IP·기기 정보는 저장하지 않는다"""

    __tablename__ = "qr_scans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    qr_code_id: Mapped[int] = mapped_column(ForeignKey("qr_codes.id", ondelete="RESTRICT"))
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_qr_scans_code_scanned_at", "qr_code_id", "scanned_at"),)


class Inquiry(TimestampMixin, Base):
    """출강·단체 견적 문의. contact_name, phone, email은 개인정보 (보관 기간 후 자동 삭제)"""

    __tablename__ = "inquiries"
    TYPES = ("outreach", "group_visit", "corporate_order", "other")
    STATUSES = ("received", "contacted", "quoted", "confirmed", "completed", "canceled")
    SOURCES = ("search", "instagram", "qr", "referral", "returning", "other")

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), server_default="received")
    organization_name: Mapped[str | None] = mapped_column(String(100))
    organization_type: Mapped[str | None] = mapped_column(String(20))
    contact_name: Mapped[str | None] = mapped_column(String(50))  # 개인정보 삭제 후에만 NULL
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    people_count: Mapped[int | None] = mapped_column(Integer)
    audience: Mapped[str | None] = mapped_column(String(20))
    preferred_schedule: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(200))
    workshop_id: Mapped[int | None] = mapped_column(
        ForeignKey("workshops.id", ondelete="SET NULL")
    )
    budget_range: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str | None] = mapped_column(String(20))
    landing_referrer: Mapped[str | None] = mapped_column(String(500))
    utm_source: Mapped[str | None] = mapped_column(String(100))
    utm_medium: Mapped[str | None] = mapped_column(String(100))
    utm_campaign: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text, server_default="")
    admin_memo: Mapped[str] = mapped_column(Text, server_default="")
    privacy_agreed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pii_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        one_of("type", TYPES),
        one_of("status", STATUSES),
        one_of("source", SOURCES),
        one_of("organization_type", ORGANIZATION_TYPES),
        one_of("audience", AUDIENCES),
        CheckConstraint("people_count IS NULL OR people_count > 0", name="people_positive"),
        # 연락처가 지워지는 건 개인정보 삭제 후뿐이다
        CheckConstraint(
            "phone IS NOT NULL OR email IS NOT NULL OR pii_purged_at IS NOT NULL",
            name="contact_required",
        ),
        CheckConstraint("contact_name IS NOT NULL OR pii_purged_at IS NOT NULL", name="contact_name_required"),
        Index("ix_inquiries_status_created_at", "status", text("created_at DESC")),
        Index("ix_inquiries_created_at_source", "created_at", "source"),
        Index(
            "ix_inquiries_pii_purge",
            "completed_at",
            postgresql_where=text("pii_purged_at IS NULL"),
        ),
    )


class Setting(TimestampMixin, Base):
    """키-값 설정. 값 형식은 백엔드(Pydantic)에서 키별로 검증한다"""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    description: Mapped[str] = mapped_column(String(200), server_default="")


class AdminUser(TimestampMixin, Base):
    """관리 화면 로그인. 비밀번호는 argon2 해시만 저장"""

    __tablename__ = "admin_users"
    ROLES = ("owner", "operator")

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    token_version: Mapped[int] = mapped_column(Integer, server_default="0")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (one_of("role", ROLES),)


class BlogPost(TimestampMixin, Base):
    """네이버 블로그 글 (RSS로 가져온다, ADR 0027). 전체 글은 블로그에 있고 여기에는 요약만.

    가져온 값(guid, title, excerpt, tags, published_at, 썸네일)은 처음 한 번만 저장한다.
    사장님이 고치는 값(display_name, kind, purposes, 판매 정보, 숨김)은 다시 가져와도 덮어쓰지 않는다.
    """

    __tablename__ = "blog_posts"
    KINDS = ("plant", "class", "outreach", "gift", "other")
    SALE_STATUSES = ("available", "reserved", "sold")

    id: Mapped[int] = mapped_column(primary_key=True)
    guid: Mapped[str] = mapped_column(String(300), unique=True)  # 원문 주소 (추적용 쿼리 제거)
    title: Mapped[str] = mapped_column(String(300))
    display_name: Mapped[str | None] = mapped_column(String(100))  # 사장님이 정한 짧은 이름
    excerpt: Mapped[str] = mapped_column(Text, server_default="")
    kind: Mapped[str] = mapped_column(String(20), server_default="other")
    tags: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))  # 블로그 원본 태그
    purposes: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))  # 정리된 목적 필터
    thumbnail_s3_key: Mapped[str | None] = mapped_column(String(300))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_hidden: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    sale_status: Mapped[str | None] = mapped_column(String(20))
    price: Mapped[int | None] = mapped_column(Integer)
    size: Mapped[str] = mapped_column(String(50), server_default="")  # 자유 입력 ("약 55cm", ADR 0028)
    plant_guide_id: Mapped[int | None] = mapped_column(ForeignKey("plant_guides.id", ondelete="SET NULL"))

    __table_args__ = (
        one_of("kind", KINDS),
        one_of("sale_status", SALE_STATUSES),
        CheckConstraint("price IS NULL OR price >= 0", name="price_non_negative"),
        # 홈·목록: 공개된 식물 글을 최신순으로
        Index("ix_blog_posts_kind_published_at", "kind", text("published_at DESC")),
    )
