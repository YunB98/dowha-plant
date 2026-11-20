# 도화 (Dowha) — 식물가게 웹사이트

🌿 https://dowha-plant.shop (준비 중)

전주의 식물가게 **도화**를 위한 웹사이트입니다.
주문은 스마트스토어에 맡기고, 홈페이지는 **새 손님을 데려오고 출강·단체 수업을 늘리는 것**에 집중합니다.

- 출강·단체 수업: 대상별 프로그램, 진행 사례, 소개서, 견적 문의
- 식물 관리 가이드: 판매 화분의 QR 카드로 연결, 검색 유입 콘텐츠
- 효과 측정: 방문·유입 경로·QR 스캔·문의 수를 대시보드로 확인

사장님이 휴대폰으로 직접 콘텐츠와 문의를 관리합니다.

이 프로젝트는 실제 가게에서 운영되는 서비스이면서, 인프라 구축·자동화·운영(DevOps) 포트폴리오입니다.

## 아키텍처 요약

```
손님 / 사장님 ──▶ Route 53 + CloudFront ──┬──▶ S3 (Next.js 정적 사이트)
                                         ├──▶ S3 (사진)
                                         └──▶ /api/*, /q/*, /umami/* ──▶ EC2 (Docker Compose)
                                                                           ├─ Nginx
                                                                           ├─ FastAPI
                                                                           ├─ Umami
                                                                           ├─ PostgreSQL ──▶ S3 백업
                                                                           └─ Prometheus, Grafana ──▶ 텔레그램 알림
운영자 ──▶ SSM Session Manager ──▶ EC2 (SQLAdmin, Grafana, Umami 포트 포워딩)
```

자세한 내용은 [docs/architecture.md](docs/architecture.md)를 참고하세요.

## 기술 스택

| 영역 | 기술 |
|---|---|
| 프론트엔드 | Next.js (정적 빌드) |
| 백엔드 | FastAPI, SQLAlchemy, Alembic |
| DB | PostgreSQL |
| 실행 환경 | Docker Compose on EC2 (t4g.small, ARM) |
| 정적 파일·사진 | S3 + CloudFront |
| 인프라 코드 | Terraform |
| CI/CD | GitHub Actions (OIDC로 AWS 인증) |
| 모니터링 | Prometheus, Grafana, 외부 헬스체크, 텔레그램 알림 |
| 방문 분석 | Umami (직접 운영), 구글 서치 콘솔, 네이버 서치어드바이저 |

## 폴더 구조

```
frontend/        Next.js — 손님용 사이트와 사장님용 모바일 관리 화면
backend/         FastAPI — REST API, 운영자용 SQLAdmin
infra/           Terraform — bootstrap(상태 저장소), modules, envs(prod, staging)
deploy/          EC2에서 실행되는 Docker Compose, Nginx, 모니터링, 백업 스크립트
.github/         GitHub Actions 워크플로
docs/            아키텍처, 요구사항, 기술 결정 기록(ADR), 운영 문서
```

## 환경

| 환경 | 위치 | 용도 |
|---|---|---|
| dev | 로컬 PC (Docker Compose) | 개발 |
| staging | AWS, 필요할 때만 생성 후 삭제 | 인프라 변경·DB 변경·복구 훈련 검증 |
| prod | AWS | 실제 운영 |

## 문서

- [요구사항 (MVP)](docs/requirements.md)
- [아키텍처](docs/architecture.md)
- [DB 설계](docs/db-schema.md)
- [API 명세](docs/api-spec.md)
- [기술 결정 기록 (ADR)](docs/adr/)
