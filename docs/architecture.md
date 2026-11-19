# 아키텍처

## 구성도

```
손님 / 사장님 ──▶ Route 53 + CloudFront ──┬──▶ S3 (Next.js 정적 사이트)
                                         ├──▶ S3 (상품·클래스 사진)
                                         └──▶ /api/* ──▶ EC2 t4g.small (Docker Compose)
                                                          ├─ Nginx
                                                          ├─ FastAPI
                                                          ├─ PostgreSQL ──▶ S3 백업 (매일, 30일 보관)
                                                          └─ Prometheus, Grafana ──▶ 텔레그램 알림
운영자 ──▶ SSM Session Manager ──▶ EC2 (SQLAdmin, Grafana 포트 포워딩)
외부 헬스체크 (Route 53 헬스체크 또는 UptimeRobot) ──▶ 텔레그램 알림
```

## 요청 흐름

| 요청 | 경로 |
|---|---|
| 페이지 | CloudFront → S3 웹사이트 버킷 |
| 상품 목록·문의 접수 | 브라우저 → CloudFront `/api/*` → EC2 Nginx → FastAPI → PostgreSQL |
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
| 상품 목록은 브라우저에서 API로 조회 | 사장님이 등록하면 즉시 반영. v2에서 저장 시 자동 재빌드 추가 예정 |
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

- 관리 화면에서 저장하면 GitHub Actions로 정적 사이트 자동 재빌드
- 트래픽 증가 시: ECS Fargate + ALB + RDS (설계 문서로만 유지)
- 네이버 클라우드에 같은 구성 배포 또는 백업 이중화
