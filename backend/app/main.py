"""도화 백엔드 API.

지금은 배포 경로(CloudFront → Nginx → FastAPI)를 확인하기 위한 헬스 체크만 있다.
API 명세는 docs/api-spec.md, 실제 문서는 /api/docs 에서 자동 생성된다.
"""

from fastapi import FastAPI

app = FastAPI(
    title="도화 API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


@app.get("/api/v1/health", tags=["system"])
def health() -> dict[str, str]:
    """외부 헬스 체크(UptimeRobot, ADR 0019)와 배포 확인용."""
    return {"status": "ok"}
