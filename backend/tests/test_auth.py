"""관리자 로그인 (docs/api-spec.md 2장 "인증")과 계정 관리 명령."""

import time
from collections.abc import Iterator

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import admin_cli
from app.auth import COOKIE_NAME, MAX_AGE, hash_password, issue_token
from app.config import Settings
from app.metrics import ADMIN_LOGINS
from app.models import AdminUser

ORIGIN = {"Origin": "https://dowha-plant.shop"}
PASSWORD = "correct-horse-battery"
LOGIN = "/api/v1/admin/auth/login"
ME = "/api/v1/admin/auth/me"


@pytest.fixture
def admin(client: TestClient, db: Session) -> AdminUser:
    user = AdminUser(username="owner", role="owner", password_hash=hash_password(PASSWORD))
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def https(client: TestClient) -> Iterator[TestClient]:
    """Secure 쿠키는 https에서만 오간다. 운영처럼 https로 요청한다."""
    client.base_url = client._merge_url("https://testserver")  # noqa: SLF001
    yield client


def login(c: TestClient, username: str = "owner", password: str = PASSWORD, headers: dict[str, str] | None = None):
    return c.post(LOGIN, json={"username": username, "password": password}, headers=ORIGIN if headers is None else headers)


def failures() -> float:
    return ADMIN_LOGINS.labels(result="failure")._value.get()


# ---------- 로그인 ----------


def test_login_sets_secure_cookie(https: TestClient, db: Session, admin: AdminUser) -> None:
    res = login(https)
    assert res.status_code == 204
    cookie = res.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    for attr in ("HttpOnly", "Secure", "SameSite=strict", "Path=/api/v1/admin", f"Max-Age={MAX_AGE}"):
        assert attr in cookie, attr
    assert PASSWORD not in cookie

    me = https.get(ME)
    assert me.status_code == 200
    assert me.json() == {"username": "owner", "role": "owner"}
    db.refresh(admin)
    assert admin.last_login_at is not None


def test_username_is_trimmed_and_lowercased(https: TestClient, admin: AdminUser) -> None:
    assert login(https, username="  Owner ").status_code == 204


@pytest.mark.parametrize(("username", "password"), [("owner", "wrong-password"), ("nobody", PASSWORD)])
def test_login_failure_does_not_say_which(https: TestClient, admin: AdminUser, username: str, password: str) -> None:
    before = failures()
    res = login(https, username, password)
    assert res.status_code == 401
    assert res.json()["error"] == {"code": "UNAUTHORIZED", "message": "아이디 또는 비밀번호가 맞지 않아요."}
    assert "set-cookie" not in res.headers
    assert failures() == before + 1


def test_login_rejects_extra_fields(https: TestClient) -> None:
    res = https.post(LOGIN, json={"username": "a", "password": "b", "role": "owner"}, headers=ORIGIN)
    assert res.status_code == 422


@pytest.mark.parametrize("headers", [{}, {"Origin": "https://evil.example"}, {"Origin": "https://dowha-plant.shop.evil.example"}])
def test_login_requires_same_origin(https: TestClient, admin: AdminUser, headers: dict[str, str]) -> None:
    res = login(https, headers=headers)
    assert res.status_code == 401
    assert "set-cookie" not in res.headers


def test_old_hash_is_upgraded_on_login(https: TestClient, db: Session, admin: AdminUser) -> None:
    admin.password_hash = PasswordHasher(time_cost=1, memory_cost=8 * 1024, parallelism=1).hash(PASSWORD)
    db.flush()
    old = admin.password_hash
    assert login(https).status_code == 204
    db.refresh(admin)
    assert admin.password_hash != old and "m=19456,t=2,p=1" in admin.password_hash


# ---------- 세션 확인 ----------


def test_me_without_cookie(https: TestClient) -> None:
    res = https.get(ME)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_cookie_is_not_sent_over_http(client: TestClient, admin: AdminUser) -> None:
    """Secure 쿠키라 http로는 브라우저가 보내지 않는다."""
    assert login(client).status_code == 204
    assert client.get(ME).status_code == 401


def test_tampered_token(https: TestClient, admin: AdminUser) -> None:
    token = issue_token(admin)
    https.cookies.set(COOKIE_NAME, token[:-2] + ("AA" if not token.endswith("AA") else "BB"))
    assert https.get(ME).status_code == 401


def test_expired_token(https: TestClient, admin: AdminUser, monkeypatch: pytest.MonkeyPatch) -> None:
    issued_at = time.time() - MAX_AGE - 60
    with monkeypatch.context() as m:
        m.setattr(time, "time", lambda: issued_at)
        token = issue_token(admin)
    https.cookies.set(COOKIE_NAME, token)
    res = https.get(ME)
    assert res.status_code == 401
    assert "만료" in res.json()["error"]["message"]


def test_token_from_other_key_is_rejected(https: TestClient, admin: AdminUser, monkeypatch: pytest.MonkeyPatch) -> None:
    """서명 키를 바꾸면 기존 토큰이 모두 무효 (전체 로그아웃)."""
    from app.config import get_settings

    with monkeypatch.context() as m:
        m.setattr(get_settings(), "session_secret", "x" * 40)
        token = issue_token(admin)
    https.cookies.set(COOKIE_NAME, token)
    assert https.get(ME).status_code == 401


def test_logout_all_invalidates_token(https: TestClient, db: Session, admin: AdminUser) -> None:
    assert login(https).status_code == 204
    admin.token_version += 1
    db.flush()
    assert https.get(ME).status_code == 401


def test_deleted_user_token(https: TestClient, db: Session, admin: AdminUser) -> None:
    assert login(https).status_code == 204
    db.delete(admin)
    db.flush()
    assert https.get(ME).status_code == 401


def test_logout_clears_cookie(https: TestClient, admin: AdminUser) -> None:
    assert login(https).status_code == 204
    res = https.post("/api/v1/admin/auth/logout", headers=ORIGIN)
    assert res.status_code == 204
    assert 'dowha_admin=""' in res.headers["set-cookie"] and "Max-Age=0" in res.headers["set-cookie"]
    assert https.get(ME).status_code == 401


def test_prod_requires_session_secret() -> None:
    with pytest.raises(RuntimeError):
        _ = Settings(app_env="prod", session_secret="").signing_key
    with pytest.raises(RuntimeError):
        _ = Settings(app_env="prod", session_secret="short").signing_key
    assert Settings(app_env="prod", session_secret="s" * 40).signing_key == "s" * 40


# ---------- 계정 관리 명령 ----------


def run_cli(db: Session, *argv: str, answers: tuple[str, ...] = ()) -> int:
    it = iter(answers)
    db.close = lambda: None  # type: ignore[method-assign]  # 테스트 트랜잭션은 fixture가 닫는다
    return admin_cli.main(list(argv), prompt=lambda _: next(it), session_factory=lambda: db)


def test_cli_create_user_then_login(https: TestClient, db: Session) -> None:
    assert run_cli(db, "create-user", "owner", answers=(PASSWORD, PASSWORD)) == 0
    user = db.scalar(select(AdminUser).where(AdminUser.username == "owner"))
    assert user is not None and user.role == "owner"
    assert user.password_hash.startswith("$argon2id$") and PASSWORD not in user.password_hash
    assert login(https).status_code == 204


@pytest.mark.parametrize(
    ("argv", "answers", "error"),
    [
        (("create-user", "owner"), ("short", "short"), "12자 이상"),
        (("create-user", "owner"), (PASSWORD, PASSWORD + "x"), "달라요"),
        (("create-user", "Owner!"), (PASSWORD, PASSWORD), "영문 소문자"),
        (("set-password", "ghost"), (PASSWORD, PASSWORD), "계정이 없어요"),
    ],
)
def test_cli_errors(db: Session, capsys: pytest.CaptureFixture[str], argv: tuple[str, ...],
                    answers: tuple[str, ...], error: str) -> None:
    assert run_cli(db, *argv, answers=answers) == 1
    assert error in capsys.readouterr().err


def test_cli_duplicate_user(db: Session, admin: AdminUser, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_cli(db, "create-user", "owner", answers=(PASSWORD, PASSWORD)) == 1
    assert "이미 있어요" in capsys.readouterr().err


def test_cli_set_password_logs_out_everywhere(https: TestClient, db: Session, admin: AdminUser) -> None:
    assert login(https).status_code == 204
    new = "another-long-password"
    assert run_cli(db, "set-password", "owner", answers=(new, new)) == 0
    assert https.get(ME).status_code == 401  # 기존 로그인 끊김
    assert login(https).status_code == 401  # 이전 비밀번호 거부
    assert login(https, password=new).status_code == 204


def test_cli_logout_all_and_list(https: TestClient, db: Session, admin: AdminUser,
                                 capsys: pytest.CaptureFixture[str]) -> None:
    assert login(https).status_code == 204
    assert run_cli(db, "logout-all", "owner") == 0
    assert https.get(ME).status_code == 401
    assert run_cli(db, "list") == 0
    out = capsys.readouterr().out
    assert "owner\towner" in out and PASSWORD not in out
