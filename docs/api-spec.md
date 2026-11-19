# API 명세

FastAPI가 OpenAPI 문서(`/api/docs`)를 자동으로 만든다. 이 문서는 개발 전 설계용이며, 구현 후에는 자동 생성 문서가 기준이 된다.

## 공통 규칙

| 항목 | 규칙 |
|---|---|
| 기본 경로 | `/api/v1` (CloudFront `/api/*` → EC2 Nginx → FastAPI) |
| 형식 | JSON, 필드 이름은 snake_case |
| 금액 | 정수, 원 단위 |
| 시간 | ISO 8601, 시간대 포함 (`2026-11-19T15:02:00+09:00`). 날짜만 있는 값은 `2026-12-24` |
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
| 403 | `FORBIDDEN` | 권한 없음 |
| 404 | `NOT_FOUND` | 대상 없음 (숨김 상품 포함) |
| 409 | `CONFLICT` | 마감된 클래스, 품절 상품 문의 등 |
| 422 | `VALIDATION_ERROR` | 입력값 검증 실패 (FastAPI 기본 응답을 위 형식으로 변환) |
| 429 | `RATE_LIMITED` | 요청 횟수 초과 |
| 500 | `INTERNAL_ERROR` | 서버 오류 (상세 내용은 로그에만 기록) |

---

## 1. 손님용 API (인증 없음)

### 분류

#### `GET /api/v1/categories`
보이는 분류를 트리 구조로 반환한다.

```json
[
  {
    "slug": "plants", "name": "식물",
    "children": [
      { "slug": "plants-small", "name": "소형" },
      { "slug": "plants-medium", "name": "중형" },
      { "slug": "plants-large", "name": "대형" }
    ]
  }
]
```

### 상품

#### `GET /api/v1/products`
| 쿼리 | 설명 |
|---|---|
| `category` | 분류 slug. 상위 분류를 주면 하위 분류 상품을 모두 반환 |
| `page`, `size` | 목록 페이지 |

`on_sale`, `sold_out` 상품만 반환한다 (`hidden` 제외). 정렬은 `sort_order`.

```json
{
  "items": [
    {
      "id": 12,
      "name": "올리브나무 (중형)",
      "category": { "slug": "plants-medium", "name": "중형" },
      "price": 85000,
      "shipping_method": "local_delivery",
      "status": "on_sale",
      "thumbnail_url": "https://dowha-plant.shop/images/products/12/a1b2.webp"
    }
  ],
  "total": 1, "page": 1, "size": 20
}
```

#### `GET /api/v1/products/{id}`
상세 정보와 사진 전체(`images: [{ "id", "image_url" }]`), `description`을 포함한다. 숨김 상품은 404.

### 클래스

#### `GET /api/v1/workshops`
`open`, `closed` 클래스를 반환한다 (`hidden` 제외). 마감된 클래스는 화면에서 "마감"으로 표시한다.

```json
[
  {
    "id": 1,
    "name": "화분 꾸미기 & 가드닝 원데이 클래스",
    "price_per_person": 30000,
    "min_people": 1, "max_people": 4,
    "duration_min": 60, "duration_max": 90,
    "is_seasonal": false,
    "status": "open",
    "thumbnail_url": "https://dowha-plant.shop/images/workshops/1/c3d4.webp"
  }
]
```

#### `GET /api/v1/workshops/{id}`
상세 정보와 사진 전체.

### 가게 정보

#### `GET /api/v1/store`
화면에 표시할 공개 설정값만 반환한다.

```json
{
  "contact": { "phone": "...", "kakao_url": "...", "instagram": "dowha_plantshop" },
  "store": { "address": "...", "hours": "..." },
  "shipping": {
    "parcel_fee": 4000,
    "local_fee": 5000,
    "local_free_threshold": 80000,
    "local_area": "전주"
  }
}
```

### 견적 계산

#### `POST /api/v1/quotes`
문의를 보내기 전에 예상 금액을 계산한다. 화면과 서버가 같은 계산 로직을 쓰도록 서버에서 계산한다.

요청:
```json
{
  "items": [{ "product_id": 12, "quantity": 1 }],
  "shipping_method": "local_delivery",
  "is_local_area": true
}
```

응답:
```json
{
  "subtotal": 85000,
  "shipping_fee": 0,
  "total_amount": 85000,
  "notices": ["8만 원 이상 구매로 배달비가 무료입니다."]
}
```

규칙:
- 택배: `parcel_fee`
- 직접 배달: `subtotal >= local_free_threshold`이면 0, 아니면 `local_fee`
- 직접 배달 상품이 있는데 `is_local_area`가 false이면 409 `CONFLICT` (전주 외 지역 배달 불가)
- 직접 배달 상품과 택배 상품이 섞여 있으면 직접 배달로 계산한다.

### 문의 접수

#### `POST /api/v1/inquiries`
`type` 값에 따라 요청 형식이 달라진다. 서버가 금액을 다시 계산해서 저장한다 (화면에서 보낸 금액은 믿지 않는다).

공통 필드:

| 필드 | 필수 | 설명 |
|---|---|---|
| `type` | O | `order` / `workshop` / `group` |
| `customer_name` | O | 1~50자 |
| `phone` | O | 휴대폰·일반 전화 번호 형식 |
| `preferred_date` | O | 오늘 이후 날짜 |
| `message` | | 1000자 이하 |
| `privacy_agreed` | O | 반드시 `true` |
| `website` | | 허니팟. 화면에서 숨긴 칸이며, 값이 있으면 스팸으로 보고 저장하지 않은 채 201을 반환한다 |

`type: "order"` 추가 필드:
```json
{
  "items": [{ "product_id": 12, "quantity": 1 }],
  "shipping_method": "local_delivery",
  "is_local_area": true,
  "address": "전주시 완산구 ...",
  "ribbon_text": "개업을 축하합니다 / 도화 드림"
}
```

`type: "workshop"` 추가 필드 (1~4명):
```json
{ "workshop_id": 1, "people_count": 2 }
```

`type: "group"` 추가 필드 (5명 이상, 단체·출강):
```json
{
  "organization": "○○초등학교",
  "people_count": 20,
  "location": "전주시 덕진구 ...",
  "workshop_id": 1
}
```

응답 `201 Created`:
```json
{ "id": 105, "type": "order", "status": "received", "total_amount": 85000, "created_at": "..." }
```

처리 후: 사장님 텔레그램으로 알림을 보낸다. 알림이 실패해도 문의 저장은 유지하고, 실패는 로그와 지표에 기록한다.

---

## 2. 사장님용 관리 API (`/api/v1/admin`)

### 인증

| 항목 | 방식 |
|---|---|
| 세션 | 로그인 시 서명된 토큰을 `HttpOnly`, `Secure`, `SameSite=Strict` 쿠키로 발급. 유효기간 14일 |
| CSRF | 같은 도메인 + `SameSite=Strict` 쿠키 + 변경 요청은 `Origin` 헤더 검사 |
| 전체 로그아웃 | `admin_users.token_version`을 올리면 기존 토큰이 모두 무효 |
| 로그인 제한 | IP당 1분 5회 |

#### `POST /api/v1/admin/auth/login`
```json
{ "username": "owner", "password": "..." }
```
성공 시 `204 No Content` + 쿠키. 실패 시 401 (아이디와 비밀번호 중 무엇이 틀렸는지 알려주지 않는다).

#### `POST /api/v1/admin/auth/logout`
쿠키를 지운다. `204`.

#### `GET /api/v1/admin/auth/me`
```json
{ "username": "owner", "role": "owner" }
```

### 요약

#### `GET /api/v1/admin/summary`
관리 화면 첫 페이지용.
```json
{ "inquiries": { "received": 3, "contacted": 2 }, "products": { "on_sale": 24, "sold_out": 3 } }
```

### 상품

| 요청 | 설명 |
|---|---|
| `GET /admin/products?category=&status=&page=` | 숨김 포함 전체 목록 |
| `GET /admin/products/{id}` | 상세 |
| `POST /admin/products` | 등록 |
| `PATCH /admin/products/{id}` | 일부 수정 (가격, 이름, 설명, 분류, 배송 방식, 순서) |
| `PATCH /admin/products/{id}/status` | `{ "status": "sold_out" }` — 품절·숨김 버튼용 |
| `DELETE /admin/products/{id}` | 삭제. 사진도 S3에서 삭제. 지난 문의의 상품 정보는 스냅샷으로 남는다 |

등록 요청:
```json
{
  "category_slug": "plants-medium",
  "name": "올리브나무 (중형)",
  "description": "햇빛을 좋아하고...",
  "price": 85000,
  "shipping_method": "local_delivery",
  "status": "on_sale"
}
```

### 사진 업로드

사진은 EC2를 거치지 않고 브라우저에서 S3로 바로 올린다.

```
1. POST /admin/uploads/presign      → 업로드 주소 발급
2. 브라우저가 S3로 직접 업로드
3. POST /admin/products/{id}/images → 업로드한 사진을 상품에 연결
```

#### `POST /api/v1/admin/uploads/presign`
```json
{ "target": "product", "content_type": "image/jpeg", "size": 2480000 }
```
| 제한 | 값 |
|---|---|
| 형식 | `image/jpeg`, `image/png`, `image/webp`, `image/heic` |
| 크기 | 10MB 이하 |
| 유효시간 | 5분 |

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

#### `POST /api/v1/admin/products/{id}/images`
```json
{ "s3_key": "uploads/tmp/....jpg" }
```
서버가 파일을 `products/{id}/`로 옮기고 행을 추가한다.

#### `PUT /api/v1/admin/products/{id}/images/order`
```json
{ "image_ids": [7, 3, 5] }
```
첫 번째 사진이 대표 사진이 된다.

#### `DELETE /api/v1/admin/products/{id}/images/{image_id}`

### 클래스

상품과 같은 구조.

| 요청 | 설명 |
|---|---|
| `GET /admin/workshops` | 숨김 포함 전체 목록 |
| `POST /admin/workshops` | 등록 |
| `PATCH /admin/workshops/{id}` | 수정 |
| `PATCH /admin/workshops/{id}/status` | `open` / `closed` / `hidden` — 시즌 클래스 열고 닫기 |
| `DELETE /admin/workshops/{id}` | 삭제 |
| `POST`, `PUT`, `DELETE /admin/workshops/{id}/images...` | 사진 (상품과 동일) |

### 분류

| 요청 | 설명 |
|---|---|
| `GET /admin/categories` | 숨김 포함 전체 트리 |
| `POST /admin/categories` | 추가 (예: 인테리어 오브제) |
| `PATCH /admin/categories/{id}` | 이름, 순서, 표시 여부 수정 |

상품이 연결된 분류는 삭제하지 않고 숨김 처리만 한다.

### 문의

#### `GET /api/v1/admin/inquiries?status=received&type=&page=`
최신순 목록.
```json
{
  "items": [
    {
      "id": 105, "type": "order", "status": "received",
      "customer_name": "김○○", "phone": "010-****-1234",
      "preferred_date": "2026-12-24",
      "summary": "올리브나무 (중형) 외 0건 · 85,000원",
      "created_at": "..."
    }
  ],
  "total": 1, "page": 1, "size": 20
}
```
목록에서는 연락처 가운데를 가린다.

#### `GET /api/v1/admin/inquiries/{id}`
공통 정보 + 종류별 정보 전체. 연락처를 가리지 않는다. 개인정보가 삭제된 문의는 해당 필드가 `null`.

#### `PATCH /api/v1/admin/inquiries/{id}`
```json
{ "status": "contacted", "admin_memo": "12/3 통화, 24일 오전 배달" }
```
상태가 바뀌면 `contacted_at`, `completed_at`을 서버가 기록한다.

### 설정

| 요청 | 설명 |
|---|---|
| `GET /admin/settings` | 사장님이 바꿀 수 있는 설정 (배송비, 연락처, 주소, 영업시간) |
| `PATCH /admin/settings` | `{ "shipping.local_fee": 6000 }`처럼 바꿀 키만 보낸다. 키별 형식 검증 |

`privacy.retention_months` 같은 운영 설정은 운영자(SQLAdmin)만 바꾼다.

---

## 3. 운영용 엔드포인트

| 경로 | 공개 여부 | 설명 |
|---|---|---|
| `GET /api/v1/health` | 공개 | 프로세스 동작 확인. 외부 헬스체크가 호출 |
| `GET /api/v1/health/ready` | 공개 | DB 연결까지 확인 |
| `GET /metrics` | **내부 전용** | Prometheus 지표. Nginx에서 외부 접근 차단 |
| `/sqladmin` | **내부 전용** | 운영자용 관리 화면. SSM 포트 포워딩으로만 접속 |
| `/api/docs` | prod에서 비활성화 | OpenAPI 문서. dev, staging에서만 연다 |

## 4. 요청 수 제한 (Nginx)

CloudFront 뒤에 있으므로 `X-Forwarded-For`에서 실제 손님 IP를 꺼내 쓴다 (`real_ip`에 CloudFront IP 대역 지정).

| 대상 | 제한 |
|---|---|
| `POST /api/v1/inquiries` | IP당 10분에 5회 |
| `POST /api/v1/quotes` | IP당 1분에 30회 |
| `POST /api/v1/admin/auth/login` | IP당 1분에 5회 |
| 그 외 | IP당 1초에 10회 (순간 20회까지 허용) |
