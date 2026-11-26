"""inquiry contact_name purgeable

contact_name도 개인정보라 보관 기간이 지나면 지워야 한다 (docs/db-schema.md).
NOT NULL이면 지울 수 없으므로 NULL을 허용하되, 개인정보를 지운 문의(pii_purged_at)에서만 비울 수 있게 한다.
기존 행은 모두 이름이 있으므로 데이터 변경은 없다.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("inquiries", "contact_name", existing_type=sa.String(length=50), nullable=True)
    op.create_check_constraint(
        op.f("ck_inquiries_contact_name_required"),
        "inquiries",
        "contact_name IS NOT NULL OR pii_purged_at IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_inquiries_contact_name_required"), "inquiries", type_="check")
    # 이름을 지운 문의가 있으면 NOT NULL로 되돌릴 수 없으므로 빈 문자열로 채운다
    op.execute("UPDATE inquiries SET contact_name = '' WHERE contact_name IS NULL")
    op.alter_column("inquiries", "contact_name", existing_type=sa.String(length=50), nullable=False)
