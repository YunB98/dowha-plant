# API 명세

FastAPI가 OpenAPI 문서(`/api/docs`)를 자동으로 만든다. 이 문서는 개발 전 설계용이며, 구현 후에는 자동 생성 문서가 기준이 된다.
(2026-11-20 방향 전환 반영, ADR 0012)

## 공통 규칙

| 항목 | 규칙 |
|---|---|
| 기본 경로 | `/api/v1` (CloudFront `/api/*` → EC2 Nginx → FastAPI) |
| 형식 | JSON, 필드 이름은 snake_case |
| 금액 | 정수, 원 단위 |
| 시간 | ISO 8601, 시간대 포함 (`2026-11-20T15:02:00+09:00`). 날짜만 있는 값은 `2026-12-24` |
| 사진 주소 | 응답에는 `s3_key` 대신 CloudFront 주소 `image_url`을 준다 |
| 목록 | `?page=1&size=20` → `{ "items": [...], "total": 42, "page": 1, "size": 20 }` |

### 오류 응답

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "입력값을 확인해주세요.",
    "details": [{ "field": "phone", "message": "연락처 형식이 올바르지 않습니다." }]
  }
}
```

| HTTP | code | 상황 |
|---|---|---|
| 400 | `BAD_REQUEST` | 요청 형식 오류 |
| 401 | `UNAUTHORIZED` | 로그인 필요, 세션 만료 |
| ~~403~~ | - | **쓰지 않는다.** CloudFront가 403을 404 페이지로 바꾸기 때문에(ADR 0021) 권한 문제도 401로 응답한다 |
| 404 | `NOT_FOUND` | 대상 없음 (비공개 포함) |
| 409 | `CONFLICT` | 공개된 가이드의 slug 변경 시도 등 |
| 422 | `VALIDATION_ERROR` | 입력값 검증 실패 (FastAPI 기본 응답을 위 형식으로 변환) |
| 429 | `RATE_LIMITED` | 요청 횟수 초과 |
| 500 | `INTERNAL_ERROR` | 서버 오류 (상세 내용은 로그에만 기록) |

---

## 1. 손님용 API (인증 없음)

### 가게 정보

#### `GET /api/v1/store`
화면에 표시할 공개 설정값만 반환한다.

```json
{
  "contact": { "phone": "...", "kakao_url": "...", "instagram": "dowha_plantshop" },
  "links": { "smartstore_url": "...", "naver_place_url": "..." },
  "store": { "address": "...", "hours": "..." },
  "outreach": { "service_area": "전주, 완주, 익산", "brochure_url": "https://dowha-plant.shop/files/brochure.pdf" }
}
```

### 클래스

#### `GET /api/v1/workshops`
`open`, `closed` 클래스를 반환한다 (`hidden` 제외).

```json
[
  {
    "id": 1,
    "name": "화분 꾸미기 & 가드닝 원데이 클래스",
    "price_per_person": 30000,
    "min_people": 1, "max_people": 4,
    "duration_min": 60, "duration_max": 90,
    "is_seasonal": false,
    "supports_outreach": true,
    "status": "open",
    "thumbnail_url": "https://dowha-plant.shop/images/workshops/1/c3d4.webp"
  }
]
```

#### `GET /api/v1/workshops/{id}`
상세 정보와 사진 전체(`images: [{ "id", "image_url", "alt_text" }]`).

### 진행 사례

#### `GET /api/v1/cases?organization_type=school&page=1`
공개된 사례를 진행 날짜 최신순으로 반환한다.

```json
{
  "items": [
    {
      "id": 7,
      "title": "초등학생 20명과 함께한 다육 화분 만들기",
      "organization_type": "school",
      "organization_display_name": "전주 ○○초등학교",
      "held_on": "2026-10-15",
      "participant_count": 20,
      "audience": "children",
      "workshop": { "id": 1, "name": "화분 꾸미기 & 가드닝 원데이 클래스" },
      "thumbnail_url": "..."
    }
  ],
  "total": 1, "page": 1, "size": 20
}
```

#### `GET /api/v1/cases/{id}`
상세 정보(`summary`)와 사진 전체.

### 작품 갤러리

#### `GET /api/v1/showcase`
공개된 작품을 `sort_order` 순으로 반환한다.
```json
[{ "id": 3, "title": "올리브나무 개업화분", "description": "...", "store_url": "https://smartstore.naver.com/...", "images": [...] }]
```

### 식물 가이드

#### `GET /api/v1/guides`
공개된 가이드 목록 (`slug`, `name`, `difficulty`, `summary`, `thumbnail_url`).

#### `GET /api/v1/guides/{slug}`
가이드 전체 내용과 사진. 비공개(`draft`)는 404.

### 문의 접수

#### `POST /api/v1/inquiries`

| 필드 | 필수 | 설명 |
|---|---|---|
| `type` | O | `outreach` / `group_visit` / `corporate_order` / `other` |
| `organization_name` | O | 1~100자 |
| `organization_type` | O | `school` / `kindergarten` / `welfare` / `public` / `company` / `other` |
| `contact_name` | O | 1~50자 |
| `phone` | O | 휴대폰·일반 전화 번호 형식 |
| `email` | | 이메일 형식 |
| `people_count` | O | 1 이상 |
| `audience` | | `children` / `teens` / `adults` / `seniors` / `mixed` |
| `preferred_schedule` | O | 200자 이하 자유 입력 |
| `location` | | `type`이 `outreach`일 때 필수 |
| `workshop_id` | | 관심 클래스 |
| `budget_range` | | 선택지 값 |
| `source` | O | `search` / `instagram` / `qr` / `referral` / `returning` / `other` |
| `attribution` | | 페이지가 자동으로 채운다: `{ "landing_referrer", "utm_source", "utm_medium", "utm_campaign" }` |
| `message` | | 1000자 이하 |
| `privacy_agreed` | O | 반드시 `true` |
| `website` | | 허니팟. 화면에서 숨긴 칸이며, 값이 있으면 스팸으로 보고 저장하지 않은 채 201을 반환한다 |

`attribution`은 손님이 처음 사이트에 들어온 시점의 값을 프론트엔드가 `sessionStorage`에 보관했다가 함께 보낸다.

응답 `201 Created`:
```json
{ "id": 105, "type": "outreach", "status": "received", "created_at": "..." }
```

처리 후: 사장님 텔레그램으로 알림을 보낸다. 알림이 실패해도 문의 저장은 유지하고, 실패는 로그와 지표에 기록한다.

### QR 연결

#### `GET /q/{code}`
CloudFront `/q/*` → EC2. JSON이 아니라 **302 리디렉션**을 반환한다. (ADR 0013)

| 상황 | 이동할 곳 | 스캔 기록 |
|---|---|---|
| 활성 코드 + 공개 가이드 연결 | `/guides/{slug}?utm_source=qr&utm_medium=card&utm_campaign={code}` | O |
| 비활성 코드, 가이드 없음, 비공개 가이드 | `/guides?utm_source=qr&utm_medium=card&utm_campaign={code}` | O |
| 없는 코드 | `/guides` | X |

- 대소문자를 구분하지 않는다 (`/q/ab12cd` = `/q/AB12CD`).
- 응답에 `Cache-Control: no-store` (CloudFront가 캐시하면 스캔이 기록되지 않는다).
- 스캔 기록에 실패해도 리디렉션은 반드시 한다.

---

## 2. 사장님용 관리 API (`/api/v1/admin`)

### 인증

| 항목 | 방식 |
|---|---|
| 세션 | 로그인 시 서명된 토큰을 `HttpOnly`, `Secure`, `SameSite=Strict` 쿠키로 발급. 유효기간 14일 |
| CSRF | 같은 도메인 + `SameSite=Strict` 쿠키 + 변경 요청은 `Origin` 헤더 검사 |
| 전체 로그아웃 | `admin_users.token_version`을 올리면 기존 토큰이 모두 무효 |
| 로그인 제한 | IP당 1분 5회 |

| 요청 | 설명 |
|---|---|
| `POST /admin/auth/login` | `{ "username", "password" }` → `204` + 쿠키. 실패 시 401 (무엇이 틀렸는지 알려주지 않는다) |
| `POST /admin/auth/logout` | 쿠키 삭제, `204` |
| `GET /admin/auth/me` | `{ "username": "owner", "role": "owner" }` |

### 요약

#### `GET /api/v1/admin/summary`
관리 화면 첫 페이지용.
```json
{
  "inquiries": { "received": 1, "contacted": 1, "this_month": 3 },
  "qr_scans": { "last_30_days": 42 },
  "content": { "cases": 6, "guides_published": 10, "showcase": 12 }
}
```

### 문의

| 요청 | 설명 |
|---|---|
| `GET /admin/inquiries?status=&type=&page=` | 최신순 목록. 연락처 가운데를 가린다 (`010-****-1234`) |
| `GET /admin/inquiries/{id}` | 전체 정보. 개인정보가 삭제된 문의는 해당 필드가 `null` |
| `PATCH /admin/inquiries/{id}` | `{ "status": "quoted", "admin_memo": "12/3 견적서 메일 발송" }`. 상태가 바뀌면 `contacted_at`, `completed_at`을 서버가 기록 |

### 콘텐츠 (클래스, 사례, 갤러리, 가이드)

모두 같은 패턴이다.

| 요청 | 클래스 | 사례 | 갤러리 | 가이드 |
|---|---|---|---|---|
| 목록 (비공개 포함) | `GET /admin/workshops` | `GET /admin/cases` | `GET /admin/showcase` | `GET /admin/guides` |
| 상세 | `GET .../{id}` | 〃 | 〃 | 〃 |
| 등록 | `POST ...` | 〃 | 〃 | 〃 |
| 수정 | `PATCH .../{id}` | 〃 | 〃 | 〃 |
| 삭제 | `DELETE .../{id}` | 〃 | 〃 | 〃 |

추가 규칙:
- `PATCH /admin/workshops/{id}`의 `status`로 시즌 클래스를 열고 닫는다.
- `PATCH /admin/cases/{id}`, `/admin/showcase/{id}`의 `is_published`로 공개 여부를 바꾼다.
- 가이드: `status`를 `published`로 처음 바꿀 때 `published_at`을 기록한다. **공개된 가이드의 `slug`는 바꿀 수 없다** (409).
- 가이드를 삭제하면 연결된 QR 코드는 `plant_guide_id`가 NULL이 되고, 스캔하면 가이드 목록으로 간다.

### 사진 업로드

사진은 EC2를 거치지 않고 브라우저에서 S3로 바로 올린다.

```
1. POST /admin/uploads/presign            → 업로드 주소 발급
2. 브라우저가 S3로 직접 업로드
3. POST /admin/{대상}/{id}/images          → 업로드한 사진을 연결
```

#### `POST /api/v1/admin/uploads/presign`
```json
{ "purpose": "image", "content_type": "image/jpeg", "size": 2480000 }
```
| 용도 | 형식 | 크기 |
|---|---|---|
| `image` | `image/jpeg`, `image/png`, `image/webp`, `image/heic` | 10MB 이하 |
| `brochure` | `application/pdf` | 20MB 이하 |

응답:
```json
{
  "upload_url": "https://...s3.amazonaws.com/...",
  "fields": { "key": "uploads/tmp/....jpg", "Content-Type": "image/jpeg", "policy": "...", "x-amz-signature": "..." },
  "s3_key": "uploads/tmp/....jpg",
  "expires_in": 300
}
```
`uploads/tmp/`에 올라온 파일은 연결되지 않으면 S3 수명 주기 규칙으로 1일 후 자동 삭제한다.

#### 사진 연결·정렬·삭제
`{대상}`은 `workshops`, `cases`, `showcase`, `guides` 중 하나.

| 요청 | 본문 | 설명 |
|---|---|---|
| `POST /admin/{대상}/{id}/images` | `{ "s3_key": "...", "alt_text": "..." }` | 파일을 `images/{대상}/{id}/`로 옮기고 연결 (CloudFront `/images/*`로만 공개, ADR 0021) |
| `PUT /admin/{대상}/{id}/images/order` | `{ "image_ids": [7, 3, 5] }` | 첫 번째가 대표 사진 |
| `PATCH /admin/images/{image_id}` | `{ "alt_text": "..." }` | 설명 수정 |
| `DELETE /admin/images/{image_id}` | | DB와 S3에서 삭제 |

### QR 코드

| 요청 | 설명 |
|---|---|
| `GET /admin/qr-codes?plant_guide_id=` | 목록. 코드별 누적·최근 30일 스캔 수 포함 |
| `POST /admin/qr-codes` | `{ "plant_guide_id": 4, "label": "2026-12 몬스테라 카드" }` → 새 코드 발급 |
| `PATCH /admin/qr-codes/{id}` | 연결 가이드 변경, `label` 수정, `is_active` 변경 |
| `GET /admin/qr-codes/{id}/image?format=png\|svg&size=` | 인쇄용 QR 이미지. 서버에서 생성 (`segno`) |

QR 코드는 삭제 API가 없다. 이미 인쇄된 카드가 있기 때문에 비활성화만 한다.

### 설정

| 요청 | 설명 |
|---|---|
| `GET /admin/settings` | 사장님이 바꿀 수 있는 설정 (연락처, 외부 링크, 주소, 영업시간, 출강 지역, 소개서) |
| `PATCH /admin/settings` | `{ "store.hours": "..." }`처럼 바꿀 키만 보낸다. 키별 형식 검증 |
| `PUT /admin/settings/brochure` | `{ "s3_key": "uploads/tmp/....pdf" }` → `files/brochure.pdf`로 옮기고 CloudFront 캐시를 무효화 |

`privacy.retention_months` 같은 운영 설정은 운영자(SQLAdmin)만 바꾼다.

---

## 3. 운영용 엔드포인트

| 경로 | 공개 여부 | 설명 |
|---|---|---|
| `GET /api/v1/health` | 공개 | 프로세스 동작 확인. 외부 헬스체크가 호출 |
| `GET /api/v1/health/ready` | 공개 | DB 연결까지 확인 |
| `GET /metrics` | **내부 전용** | Prometheus 지표. Nginx에서 외부 접근 차단 |
| `/sqladmin` | **내부 전용** | 운영자용 관리 화면. SSM 포트 포워딩으로만 접속 |
| `/umami/script.js`, `/umami/api/send` | 공개 | 방문 분석 스크립트와 수집 (ADR 0014) |
| Umami 관리 화면 | **내부 전용** | SSM 포트 포워딩으로만 접속 |
| `/api/docs` | prod에서 비활성화 | OpenAPI 문서. dev, staging에서만 연다 |

### 비즈니스 지표 (Prometheus)
| 지표 | 설명 |
|---|---|
| `dowha_inquiries_created_total{type, source}` | 문의 접수 수 |
| `dowha_qr_scans_total{result}` | QR 스캔 수 (`guide`, `fallback`, `unknown`) |
| `dowha_notifications_failed_total{channel}` | 알림 실패 수 (알림 대상) |

월별 추이 같은 장기 집계는 Grafana에서 PostgreSQL을 직접 조회한다.

## 4. 요청 수 제한 (Nginx)

CloudFront 뒤에 있으므로 `X-Forwarded-For`에서 실제 손님 IP를 꺼내 쓴다 (`real_ip`에 CloudFront IP 대역 지정).

| 대상 | 제한 |
|---|---|
| `POST /api/v1/inquiries` | IP당 10분에 5회 |
| `POST /api/v1/admin/auth/login` | IP당 1분에 5회 |
| `GET /q/*` | IP당 1초에 5회 |
| 그 외 | IP당 1초에 10회 (순간 20회까지 허용) |
