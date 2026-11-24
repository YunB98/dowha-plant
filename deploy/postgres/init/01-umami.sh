#!/bin/sh
# 데이터 볼륨이 비어 있을 때(최초 1회)만 실행된다.
# 앱(dowha)과 Umami가 같은 PostgreSQL을 쓰고 데이터베이스와 사용자만 나눈다 (ADR 0022).
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v umami_password="$UMAMI_DB_PASSWORD" <<'SQL'
CREATE ROLE umami LOGIN PASSWORD :'umami_password';
CREATE DATABASE umami OWNER umami;
REVOKE ALL ON DATABASE dowha FROM PUBLIC;
SQL
