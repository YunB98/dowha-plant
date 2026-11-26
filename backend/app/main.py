"""도화 백엔드 API.

API 명세는 docs/api-spec.md, 실제 문서는 /api/docs 에서 자동 생성된다 (prod에서는 닫는다).
"""

import logging

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import errors, inquiries
from app.config import get_settings
from app.db import get_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
# httpx는 요청 URL을 INFO로 남기는데, 텔레그램 URL에는 봇 토큰이 들어 있다
logging.getLogger("httpx").setLevel(logging.WARNING)

settings = get_settings()

app = FastAPI(
    title="도화 API",
    version="0.1.0",
    docs_url=None if settings.is_prod else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.is_prod else "/api/openapi.json",
)
errors.register(app)
app.include_router(inquiries.router)

# Prometheus 수집 경로. Nginx는 /api/, /q/, /umami/ 만 넘기므로 밖에서는 닿지 않는다.
app.mount("/metrics", make_asgi_app())


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
