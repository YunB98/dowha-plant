"""도화 백엔드 API.

API 명세는 docs/api-spec.md, 실제 문서는 /api/docs 에서 자동 생성된다.
"""

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db

app = FastAPI(
    title="도화 API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


@app.get("/api/v1/health", tags=["system"])
def health() -> dict[str, str]:
    """프로세스가 살아 있는지 (컨테이너 헬스 체크). DB는 확인하지 않는다."""
    return {"status": "ok"}


@app.get("/api/v1/health/ready", tags=["system"])
def ready(db: Session = Depends(get_db)) -> JSONResponse:
    """요청을 처리할 수 있는지 (DB 연결 포함). 배포 확인과 외부 헬스 체크(UptimeRobot)용."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse({"status": "unavailable", "database": "error"}, status_code=503)
    return JSONResponse({"status": "ok", "database": "ok"})
