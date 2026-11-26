#!/bin/sh
# 컨테이너 시작: 마이그레이션을 먼저 적용하고 API를 띄운다.
# api 컨테이너는 한 개뿐이라 동시에 두 곳에서 마이그레이션이 돌 일이 없다.
# 마이그레이션이 실패하면 API가 뜨지 않고, 헬스 체크 실패로 배포가 멈춘다 (기존 컨테이너는 compose가 교체 전까지 유지).
set -eu

alembic upgrade head

# 메모리 160MB 제한이라 워커 1개 (ADR 0022)
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 \
  --proxy-headers --forwarded-allow-ips '*'
