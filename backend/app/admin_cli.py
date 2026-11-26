"""관리자 계정 관리 명령. 서버에서 사장님(또는 운영자)이 직접 실행한다 (deploy/README.md).

    docker compose exec api python -m app.admin_cli create-user owner --role owner
    docker compose exec api python -m app.admin_cli set-password owner
    docker compose exec api python -m app.admin_cli logout-all owner
    docker compose exec api python -m app.admin_cli list

비밀번호는 화면에 보이지 않게 직접 입력받는다. 명령 인자·환경 변수·파일로 받지 않는다
(셸 기록과 SSM 실행 기록에 남기 때문이다).
"""

import argparse
import getpass
import re
import sys
from collections.abc import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import AdminUser

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,50}$")
MIN_PASSWORD = 12


class CliError(Exception):
    pass


def read_password(prompt: Callable[[str], str]) -> str:
    password = prompt("새 비밀번호 (12자 이상): ")
    if len(password) < MIN_PASSWORD:
        raise CliError(f"비밀번호는 {MIN_PASSWORD}자 이상이어야 해요.")
    if len(password) > 200:
        raise CliError("비밀번호는 200자 이하여야 해요.")
    if prompt("한 번 더 입력: ") != password:
        raise CliError("두 비밀번호가 달라요.")
    return password


def _get_user(db: Session, username: str) -> AdminUser:
    user = db.scalar(select(AdminUser).where(AdminUser.username == username))
    if user is None:
        raise CliError(f"'{username}' 계정이 없어요.")
    return user


def create_user(db: Session, username: str, role: str, password: str) -> AdminUser:
    if not USERNAME_RE.fullmatch(username):
        raise CliError("아이디는 영문 소문자·숫자·밑줄 3~50자예요.")
    if role not in AdminUser.ROLES:
        raise CliError(f"역할은 {', '.join(AdminUser.ROLES)} 중 하나예요.")
    if db.scalar(select(AdminUser.id).where(AdminUser.username == username)):
        raise CliError(f"'{username}' 계정이 이미 있어요. 비밀번호를 바꾸려면 set-password를 쓰세요.")
    user = AdminUser(username=username, role=role, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    return user


def set_password(db: Session, username: str, password: str) -> None:
    """비밀번호를 바꾸면 다른 기기의 로그인도 모두 끊는다."""
    user = _get_user(db, username)
    user.password_hash = hash_password(password)
    user.token_version += 1
    db.commit()


def logout_all(db: Session, username: str) -> None:
    user = _get_user(db, username)
    user.token_version += 1
    db.commit()


def main(argv: Sequence[str] | None = None, prompt: Callable[[str], str] = getpass.getpass,
         session_factory: Callable[[], Session] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.admin_cli", description="관리자 계정 관리")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-user", help="계정 만들기")
    create.add_argument("username")
    create.add_argument("--role", choices=AdminUser.ROLES, default="owner")
    sub.add_parser("set-password", help="비밀번호 바꾸기 (모든 기기 로그아웃)").add_argument("username")
    sub.add_parser("logout-all", help="모든 기기 로그아웃").add_argument("username")
    sub.add_parser("list", help="계정 목록")
    args = parser.parse_args(argv)

    if session_factory is None:
        from app.db import SessionLocal

        session_factory = SessionLocal

    db = session_factory()
    try:
        if args.command == "create-user":
            create_user(db, args.username, args.role, read_password(prompt))
            print(f"'{args.username}' 계정을 만들었어요 ({args.role}).")
        elif args.command == "set-password":
            set_password(db, args.username, read_password(prompt))
            print("비밀번호를 바꿨어요. 모든 기기에서 다시 로그인해야 해요.")
        elif args.command == "logout-all":
            logout_all(db, args.username)
            print("모든 기기에서 로그아웃했어요.")
        else:
            for u in db.scalars(select(AdminUser).order_by(AdminUser.id)):
                last = u.last_login_at.isoformat(timespec="minutes") if u.last_login_at else "-"
                print(f"{u.username}\t{u.role}\t마지막 로그인 {last}")
    except CliError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
