"""사장님 관리 화면 로그인 (docs/api-spec.md 2장 "인증").

- 세션: 서명된 토큰(itsdangerous)을 HttpOnly·Secure·SameSite=Strict 쿠키로. 유효기간 14일
  토큰에는 사용자 id와 token_version만 들어 있다. 비밀번호를 바꾸거나 전체 로그아웃하면
  token_version이 올라가서 이전 토큰이 모두 무효가 된다.
- CSRF: SameSite=Strict + 상태를 바꾸는 요청은 Origin 헤더가 사이트 주소와 같아야 한다
- 비밀번호: argon2id. 메모리 19MiB·2회 (OWASP 권장 최소값). 기본값(64MiB)은 api 컨테이너
  메모리 한도(160MB)에서 로그인 두 건이 겹치면 위험하다
- 실패 응답은 아이디가 틀렸는지 비밀번호가 틀렸는지 알려 주지 않는다. 없는 아이디도 해시 검증을
  한 번 해서 응답 시간으로도 구분되지 않게 한다
- 403은 쓰지 않는다 (CloudFront가 404 페이지로 바꾼다, ADR 0021). 권한 문제도 401
- 시도 횟수 제한은 Nginx (IP당 1분 5회). 해시 계산은 한 번에 하나씩 (메모리·CPU 보호)
"""

import logging
import threading
from datetime import UTC, datetime
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.metrics import ADMIN_LOGINS
from app.models import AdminUser

log = logging.getLogger("dowha.auth")

COOKIE_NAME = "dowha_admin"
COOKIE_PATH = "/api/v1/admin"  # 관리 API에만 쿠키를 보낸다
MAX_AGE = 14 * 24 * 60 * 60
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

hasher = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)
# 해시 계산은 한 번에 하나씩. 동시 로그인이 몰려도 해시 메모리는 19MiB 하나, CPU는 한 코어만 쓴다.
# 로그인은 드물어서 기다려도 문제없다. (해제한 메모리를 OS에 돌려주는 설정은 Dockerfile MALLOC_MMAP_THRESHOLD_)
_hash_lock = threading.Lock()
# 없는 아이디로 로그인할 때도 같은 시간이 걸리게 비교할 해시
_DUMMY_HASH = hasher.hash("dowha-timing-equalizer")


def hash_password(password: str) -> str:
    with _hash_lock:
        return hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    with _hash_lock:
        try:
            return hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().signing_key, salt="dowha-admin-session")


def issue_token(user: AdminUser) -> str:
    return _serializer().dumps({"uid": user.id, "ver": user.token_version})


def unauthorized(message: str | None = None) -> HTTPException:
    return HTTPException(status_code=401, detail=message)


def check_origin(request: Request) -> None:
    """상태를 바꾸는 요청은 우리 사이트에서 온 것만 받는다 (CSRF)."""
    if request.method in SAFE_METHODS:
        return
    allowed = get_settings().public_base_url.rstrip("/")
    if request.headers.get("origin") != allowed:
        log.warning("admin request with bad origin: %s %s", request.method, request.url.path)
        raise unauthorized("허용되지 않은 요청이에요.")


def current_admin(request: Request, db: Session = Depends(get_db)) -> AdminUser:
    """관리 API 공통 의존성. 이후 관리 라우터는 dependencies=[Depends(current_admin)]로 막는다."""
    check_origin(request)
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise unauthorized()
    try:
        data: dict[str, Any] = _serializer().loads(token, max_age=MAX_AGE)
    except BadSignature:  # 위조, 만료(SignatureExpired) 모두
        raise unauthorized("로그인이 만료됐어요. 다시 로그인해주세요.") from None
    user = db.get(AdminUser, data.get("uid"))
    if user is None or user.token_version != data.get("ver"):
        raise unauthorized("로그인이 만료됐어요. 다시 로그인해주세요.")
    return user


# ---------- API ----------

router = APIRouter(prefix="/api/v1/admin/auth", tags=["admin-auth"])


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class MeOut(BaseModel):
    username: str
    role: str


@router.post("/login", status_code=204, response_class=Response)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> Response:
    check_origin(request)
    user = db.scalar(select(AdminUser).where(AdminUser.username == body.username.strip().lower()))
    valid = verify_password(user.password_hash if user else _DUMMY_HASH, body.password)
    if user is None or not valid:
        ADMIN_LOGINS.labels(result="failure").inc()
        log.warning("admin login failed: username=%r", body.username[:50])
        raise unauthorized("아이디 또는 비밀번호가 맞지 않아요.")

    if hasher.check_needs_rehash(user.password_hash):  # 해시 설정을 바꾼 뒤 첫 로그인에서 갱신
        user.password_hash = hash_password(body.password)
    user.last_login_at = datetime.now(UTC)
    db.commit()
    ADMIN_LOGINS.labels(result="success").inc()
    log.info("admin login: username=%s", user.username)

    response = Response(status_code=204)
    response.set_cookie(
        COOKIE_NAME,
        issue_token(user),
        max_age=MAX_AGE,
        path=COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite="strict",
    )
    return response


@router.post("/logout", status_code=204, response_class=Response)
def logout(request: Request) -> Response:
    check_origin(request)
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, secure=True, httponly=True, samesite="strict")
    return response


@router.get("/me")
def me(user: AdminUser = Depends(current_admin)) -> MeOut:
    return MeOut(username=user.username, role=user.role)
