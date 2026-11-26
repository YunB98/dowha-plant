"""seed workshops and settings

초기 데이터 (docs/db-schema.md, 친구 답변 2026-11-19 기준).
연락처·주소처럼 아직 받지 못한 값은 넣지 않는다. 관리 화면에서 사장님이 채운다.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

workshops = sa.table(
    "workshops",
    sa.column("name", sa.String),
    sa.column("price_per_person", sa.Integer),
    sa.column("is_seasonal", sa.Boolean),
    sa.column("sort_order", sa.Integer),
)

settings = sa.table(
    "settings",
    sa.column("key", sa.String),
    sa.column("value", JSONB),
    sa.column("description", sa.String),
)

WORKSHOPS = [
    {"name": "화분 꾸미기 & 가드닝", "price_per_person": 30000, "is_seasonal": False, "sort_order": 1},
    {"name": "수형 잡기", "price_per_person": 35000, "is_seasonal": False, "sort_order": 2},
    {"name": "크리스마스 생화 리스", "price_per_person": 40000, "is_seasonal": True, "sort_order": 3},
]

SETTINGS = [
    {"key": "contact.instagram", "value": "dowha_plantshop", "description": "인스타그램 계정"},
    {"key": "outreach.service_area", "value": "전주, 완주, 익산", "description": "출강 가능 지역"},
    {
        "key": "privacy.retention_months",
        "value": 6,
        "description": "완료·취소 문의의 개인정보 보관 개월 수 (법령 확인 필요)",
    },
]


def upgrade() -> None:
    op.bulk_insert(workshops, WORKSHOPS)
    op.bulk_insert(settings, SETTINGS)


def downgrade() -> None:
    names = [w["name"] for w in WORKSHOPS]
    keys = [s["key"] for s in SETTINGS]
    op.execute(workshops.delete().where(workshops.c.name.in_(names)))
    op.execute(settings.delete().where(settings.c.key.in_(keys)))
