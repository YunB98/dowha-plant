# 0003. 백엔드로 FastAPI 사용

- 상태: 채택
- 날짜: 2026-11-19

## 배경
후보: FastAPI, Django, Express/NestJS, Spring Boot, Go.
이전 프로젝트에서 Spring Boot를 써봤다.

## 결정
FastAPI(Python)를 사용한다. DB는 PostgreSQL, ORM은 SQLAlchemy, 마이그레이션은 Alembic을 쓴다.

## 이유
- API가 상품 조회, 문의 접수, 관리 기능 정도로 단순하다.
- Spring Boot는 메모리를 300~500MB 사용해, 2GB 서버 한 대에 DB와 모니터링까지 함께 올리기에 부담이 크다.
- FastAPI는 가볍고 API 문서(Swagger)가 자동으로 생성된다.

## 결과
- 관리 화면이 기본 제공되지 않는다. 운영자용은 SQLAdmin, 사장님용은 Next.js로 만든다 (ADR 0007).
