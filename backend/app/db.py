from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

# PostgreSQL max_connections=20을 앱과 Umami가 나눠 쓴다 (ADR 0022). 앱은 최대 5개만 쓴다.
engine = create_engine(
    get_settings().sqlalchemy_url,
    pool_size=3,
    max_overflow=2,
    pool_pre_ping=True,  # DB 재시작 후 끊긴 연결을 다시 맺는다
    pool_recycle=1800,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI 의존성: 요청마다 세션 하나."""
    with SessionLocal() as session:
        yield session
