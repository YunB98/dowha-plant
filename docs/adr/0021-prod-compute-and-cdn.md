# 0021. prod 서버와 CDN 구성

- 상태: 채택
- 날짜: 2026-11-23

## 서버 (`modules/compute`)
| 결정 | 이유 |
|---|---|
| EC2 `t4g.small` (ARM, 2GB) + Amazon Linux 2023, 스왑 1GB | 컨테이너 여러 개(Nginx, FastAPI, PostgreSQL, Umami, 모니터링)를 한 대에서 돌린다 (ADR 0002) |
| **SSH 포트 없음**, SSM Session Manager로만 접속 | 키 관리 불필요, 인바운드 22번을 열지 않는다 |
| 인바운드는 **CloudFront origin-facing 프리픽스 리스트의 443만** | 서버를 인터넷에 직접 노출하지 않는다. 프리픽스 리스트가 보안 그룹 규칙 한도(60)의 약 55를 차지하는 점에 주의 |
| IMDSv2 강제 (hop limit 2) | SSRF로 인스턴스 자격 증명이 새는 것을 막는다. hop 2는 컨테이너 안에서 IMDS에 닿기 위해서 |
| EIP(고정 IP) + `origin.dowha-plant.shop` A 레코드 | CloudFront 오리진 주소를 고정한다 |
| EBS gp3 20GB 암호화, **DLM 일일 스냅샷 7개** (KST 03:00) | RPO 24시간 (DB 덤프와 별도로 디스크 전체 복구 수단) |
| `ami`, `user_data` 변경 무시, 종료 방지 켬 | 새 AMI가 나왔다고 운영 서버가 교체되지 않게 한다. 교체는 runbook에 따라 의도적으로 한다 |
| ECR `IMMUTABLE` 태그, 푸시 시 취약점 스캔, 최근 10개만 보관 | 같은 태그로 다른 이미지를 덮어쓰지 못한다 (커밋 SHA 태그) |
| Docker Compose 버전 고정 (출시 후 2주 이상 지난 버전) | 막 나온 버전의 버그를 피한다 |

### 서버 IAM 권한 (최소 권한)
| 대상 | 권한 |
|---|---|
| media 버킷 | 읽기·쓰기·삭제 (presigned URL, 임시 파일 이동) |
| backup 버킷 | 읽기·쓰기 (삭제는 수명 주기 규칙) |
| site 버킷 | `files/*` 쓰기만 (소개서 PDF) |
| SSM 파라미터 | `/dowha-plant/prod/*` 읽기 |
| ECR | 백엔드 저장소 pull |
| Route 53 | `_acme-challenge.origin.dowha-plant.shop` 레코드만 변경 (Let's Encrypt DNS-01) |
| CloudFront | 이 배포의 캐시 무효화만 |

오리진 인증서는 Let's Encrypt **DNS-01** 방식으로 받는다. HTTP-01은 80번 포트를 인터넷에 열어야 해서 쓰지 않는다.

## CDN (`modules/cdn`)
| 경로 | 대상 | 캐시 |
|---|---|---|
| `/api/*`, `/q/*`, `/umami/*` | EC2 (`origin.dowha-plant.shop`, HTTPS) | 안 함 |
| `/images/*` | S3 media 버킷 (OAC) | 함 |
| 그 외 | S3 site 버킷 (OAC) | 함 |

- **오리진 비밀 헤더**: CloudFront가 `X-Origin-Verify` 헤더를 붙이고, Nginx가 SSM 파라미터 값과 비교한다. 보안 그룹으로 CloudFront만 허용하더라도, 다른 사람의 CloudFront 배포를 거친 요청까지 막기 위해서다.
- 인증서: us-east-1 ACM, `dowha-plant.shop` + `www`, DNS 검증 자동화.
- CloudFront Function: `www` → apex 301 이동, 폴더형 주소에 `index.html` 붙이기. 그래서 **Next.js는 `trailingSlash: true`로 빌드**한다.
- 보안 헤더(HSTS 등)는 AWS 관리형 `SecurityHeadersPolicy`를 쓴다.
- HTTP/3, IPv6 사용. `PriceClass_200` (한국 엣지 포함).
- 접근 로그, WAF는 비용 때문에 쓰지 않는다. 트래픽이 늘거나 공격이 보이면 다시 검토한다.

### 오류 페이지와 API의 제약
CloudFront 오류 페이지 설정은 **배포 전체**에 적용된다.
- S3에 없는 파일은 403으로 돌아오므로 403 → `/404.html`(404)로 바꾼다. **그래서 백엔드 API는 403을 응답하지 않는다** (권한 문제도 401로 응답). 403을 쓰면 JSON 대신 404 페이지가 나간다.
- 502·503·504 → `/error.html`. 서버가 내려가도 손님에게 안내 페이지를 보여주고, QR 스캔도 여기서 가이드 목록으로 안내한다 (ADR 0013).

### 사진 경로
`/images/*`만 media 버킷으로 가므로, 공개할 사진은 버킷의 `images/` 아래에 둔다 (`images/{대상}/{id}/...`). `uploads/tmp/`는 CloudFront로 닿지 않는다.

## 비용 (서울, 온디맨드, AWS 가격표 기준)
| 항목 | 단가 | 월 (730시간) |
|---|---|---|
| EC2 t4g.small | 0.0208달러/시간 | 약 15.2달러 |
| 공인 IPv4 (EIP) | 0.005달러/시간 | 약 3.7달러 |
| EBS gp3 20GB | 0.0912달러/GB-월 | 약 1.8달러 |
| EBS 스냅샷 (증분) | | 약 0.5달러 |
| Route 53 호스팅 영역 (global 스택) | | 0.5달러 |
| CloudFront, S3, ECR, SSM | 소규모 트래픽 | 약 0~1달러 |
| **합계** | | **약 21~23달러 (약 3만 원)** |

- 100달러 크레딧으로 약 4~5개월 운영할 수 있다.
- **조직의 예산 차단 SCP(월 20달러, ADR 0017)보다 높다.** 예상 비용이 한도에 가까워지면 새 유료 리소스 생성이 막히므로, apply 전에 예산을 30달러 이상으로 올린다.
- 1년 이상 운영이 확실해지면 Savings Plans로 EC2 비용을 줄이는 것을 검토한다.
