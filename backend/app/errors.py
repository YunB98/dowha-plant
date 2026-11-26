"""공통 오류 응답 (docs/api-spec.md "오류 응답").

{"error": {"code": "...", "message": "...", "details": [{"field": "...", "message": "..."}]}}

403은 쓰지 않는다. CloudFront가 403을 404 페이지로 바꾸기 때문이다 (ADR 0021).
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("dowha")

CODES = {
    400: ("BAD_REQUEST", "요청 형식이 올바르지 않아요."),
    401: ("UNAUTHORIZED", "로그인이 필요해요."),
    404: ("NOT_FOUND", "찾는 항목이 없어요."),
    405: ("BAD_REQUEST", "지원하지 않는 요청이에요."),
    409: ("CONFLICT", "다른 데이터와 충돌해요."),
    422: ("VALIDATION_ERROR", "입력값을 확인해주세요."),
    429: ("RATE_LIMITED", "요청이 너무 많아요. 잠시 후 다시 시도해주세요."),
    500: ("INTERNAL_ERROR", "일시적인 오류가 생겼어요. 잠시 후 다시 시도해주세요."),
    503: ("SERVICE_UNAVAILABLE", "잠시 사용할 수 없어요. 잠시 후 다시 시도해주세요."),
}

# pydantic 오류 종류별 기본 한글 메시지. 직접 쓴 검증(ValueError)은 그 메시지를 그대로 쓴다.
PYDANTIC_MESSAGES = {
    "missing": "필수 항목이에요.",
    "string_too_short": "내용을 입력해주세요.",
    "string_too_long": "{max_length}자 이하로 입력해주세요.",
    "literal_error": "선택할 수 있는 값이 아니에요.",
    "int_parsing": "숫자로 입력해주세요.",
    "int_type": "숫자로 입력해주세요.",
    "greater_than_equal": "{ge} 이상으로 입력해주세요.",
    "less_than_equal": "{le} 이하로 입력해주세요.",
    "bool_parsing": "참/거짓 값이어야 해요.",
    "extra_forbidden": "알 수 없는 항목이에요.",
    "json_invalid": "JSON 형식이 올바르지 않아요.",
}


def error_body(status: int, details: list[dict[str, str]] | None = None, message: str | None = None) -> dict[str, Any]:
    code, default_message = CODES.get(status, CODES[500])
    body: dict[str, Any] = {"code": code, "message": message or default_message}
    if details:
        body["details"] = details
    return {"error": body}


def _field_name(loc: tuple[Any, ...]) -> str:
    # ("body", "attribution", "utm_source") → "attribution.utm_source"
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts) or "body"


def _message(err: dict[str, Any]) -> str:
    if err["type"] == "value_error":
        # 검증 함수에서 raise ValueError("...") 한 메시지 ("Value error, " 접두어 제거)
        return str(err.get("ctx", {}).get("error", err["msg"]))
    template = PYDANTIC_MESSAGES.get(err["type"])
    if template is None:
        return "입력값이 올바르지 않아요."
    try:
        return template.format(**err.get("ctx", {}))
    except (KeyError, IndexError):
        return template


def register(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"field": _field_name(e["loc"]), "message": _message(e)} for e in exc.errors()]
        return JSONResponse(error_body(422, details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        status = 401 if exc.status_code == 403 else exc.status_code
        message = exc.detail if isinstance(exc.detail, str) and exc.detail not in ("Not Found", "Forbidden") else None
        return JSONResponse(error_body(status, message=message), status_code=status, headers=exc.headers)

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error: %s %s", request.method, request.url.path)
        return JSONResponse(error_body(500), status_code=500)
