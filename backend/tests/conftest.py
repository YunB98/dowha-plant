"""테스트는 실제 PostgreSQL로 돌린다 (CHECK 제약, 부분 인덱스, JSONB는 SQLite로 확인할 수 없다).

- 로컬: docker run -d --name dowha-pg-dev -e POSTGRES_USER=dowha -e POSTGRES_PASSWORD=dowha \\
          -e POSTGRES_DB=dowha -p 127.0.0.1:55432:5432 postgres:17.5-alpine
        DATABASE_URL=postgresql://dowha:dowha@127.0.0.1:55432/dowha pytest
- CI: deploy 워크플로의 postgres 서비스 컨테이너
테스트 DB는 매 실행마다 비우고 마이그레이션으로 다시 만든다. 운영 DB 주소를 넣지 말 것.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


@pytest.fixture(scope="session", autouse=True)
def migrated_db() -> Iterator[None]:
    url = os.environ.get("DATABASE_URL", "")
    if "127.0.0.1" not in url and "localhost" not in url:
        pytest.exit("테스트는 로컬/CI PostgreSQL에서만 실행한다 (DATABASE_URL 확인)", returncode=2)
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture
def db() -> Iterator[Session]:
    """테스트마다 트랜잭션을 열고 끝나면 되돌린다."""
    from app.db import engine

    with engine.connect() as conn:
        trans = conn.begin()
        session = Session(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            trans.rollback()
