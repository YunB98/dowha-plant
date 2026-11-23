# 아키텍처

## 구성도

```
손님 / 사장님 ──▶ Route 53 + CloudFront ──┬──▶ S3 (Next.js 정적 사이트, 소개서 PDF)
                                         ├──▶ S3 (사진)
                                         └──▶ /api/*, /q/*, /umami/* ──▶ EC2 t4g.micro (Docker Compose, ADR 0022)
                                                                           ├─ Nginx
                                                                           ├─ FastAPI
                                                                           ├─ Umami (방문 분석)
                                                                           ├─ PostgreSQL ──▶ S3 백업 (매일, 30일 보관)
                                                                           ├─ Prometheus, Alertmanager ──▶ 텔레그램 알림
                                                                           └─ Grafana (필요할 때만 실행)
FastAPI ──(콘텐츠 공개)──▶ GitHub Actions ──▶ 정적 사이트 재빌드 ──▶ S3 + CloudFront 캐시 무효화
운영자 ──▶ SSM Session Manager ──▶ EC2 (SQLAdmin, Grafana, Umami 관리 화면 포트 포워딩)
외부 헬스체크 (UptimeRobot, ADR 0019) ──▶ 텔레그램 알림
```

## 요청 흐름

| 요청 | 경로 |
|---|---|
| 페이지 | CloudFront → S3 웹사이트 버킷 |
| 문의 접수, 클래스·설정 조회 | 브라우저 → CloudFront `/api/*` → EC2 Nginx → FastAPI → PostgreSQL |
| QR 스캔 | CloudFront `/q/*` (캐시 안 함) → FastAPI → 스캔 기록 → 302 → 가이드 페이지 |
| 방문 분석 | 브라우저 → CloudFront `/umami/*` → Umami (스크립트, 수집 경로만 공개) |
| 가이드·사례 공개 | 관리 화면 → FastAPI → GitHub `repository_dispatch` → 재빌드 → S3 배포 (약 3~5분) |
| 사진 보기 | CloudFront → S3 사진 버킷 |
| 사진 올리기 | FastAPI가 presigned URL 발급 → 브라우저가 S3에 직접 업로드 |
| 운영자 접속 | SSM 세션, 포트 포워딩 (SSH 포트 없음) |

## 설계 결정

| 결정 | 이유 |
|---|---|
| CloudFront 단일 도메인, `/api/*`는 EC2로 | CORS 불필요, EC2를 외부에 직접 노출하지 않음 |
| CloudFront → EC2 구간 HTTPS + 비밀 헤더 | `origin` 서브도메인에 Let's Encrypt 인증서, 비밀 헤더가 없는 요청은 Nginx에서 거부 |
| SSH 대신 SSM | 접속 키 관리 불필요, 관리 도구를 외부에 공개하지 않음 |
| 사진은 S3 직접 업로드 | 큰 파일이 EC2를 거치지 않음 |
| NAT Gateway, RDS, 로드밸런서 미사용 | 월 7만 원 이상 절감, 대신 백업·모니터링을 직접 운영 |
| 가이드·사례·갤러리는 빌드 시 HTML로 생성, 공개하면 자동 재빌드 | 검색 노출이 목표라 HTML에 내용이 있어야 함 (ADR 0015) |
| QR은 `/q/{code}` 간접 연결 | 인쇄된 QR이 깨지지 않고 스캔 수를 셀 수 있음 (ADR 0013) |
| Umami 직접 운영 | 쿠키 없는 방문 분석, 데이터 직접 소유 (ADR 0014) |
| 외부 헬스체크 | 같은 EC2의 모니터링은 서버가 멈추면 알림을 못 보냄 |

## 장애 대응 목표

| 항목 | 목표 | 방법 |
|---|---|---|
| RPO (데이터 손실 허용) | 24시간 | 매일 `pg_dump` → S3, EBS 스냅샷 |
| RTO (복구 시간) | 1시간 | Terraform + `user_data`로 새 서버 생성 후 백업 복원 |

복구 절차는 `docs/runbook.md`에 정리하고, staging에서 실제 복구 훈련을 해서 걸린 시간을 기록한다.

## 환경

| 환경 | 구성 |
|---|---|
| dev | 로컬 Docker Compose |
| staging | `infra/envs/staging`, prod와 같은 모듈, 필요할 때만 `apply` 후 `destroy` |
| prod | `infra/envs/prod` |

## 도메인

- `dowha-plant.shop` (가비아 등록, ADR 0009)
- 네임서버를 Route 53 호스팅 영역으로 위임

| 주소 | 용도 |
|---|---|
| `dowha-plant.shop`, `www.dowha-plant.shop` | 사이트 (CloudFront) |
| `origin.dowha-plant.shop` | CloudFront → EC2 연결용 |
| `staging.dowha-plant.shop` | staging 환경 (필요할 때만) |

## 이후 확장 (v2 이후)

- 트래픽 증가 시: ECS Fargate + ALB + RDS (설계 문서로만 유지)
- 네이버 클라우드에 같은 구성 배포 또는 백업 이중화
