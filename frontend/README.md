# frontend — 손님 사이트 (Next.js 정적 빌드)

디자인 원본은 사장님 쪽에서 만든 프로토타입이다 (`github.com/cd1070k987654321-beep/dohwa-frontend`, ADR 0028).
이 폴더는 그 디자인을 Next.js로 옮겨 빌드 시 HTML로 만들고 S3 + CloudFront로 배포한다 (ADR 0015, 0021).

## 실행
```bash
npm ci
npm run dev        # http://localhost:3000
npm run build      # out/ 에 정적 사이트 (index.html, 404.html, error.html, _next/…)
npm run typecheck
CONTENT_SOURCE=api npm run build   # 운영 API 내용으로 빌드 (CI와 같다)
```

## 내용은 어디서 오나 (`lib/content.ts`)
| `CONTENT_SOURCE` | 내용 | 쓰는 곳 |
|---|---|---|
| `api` | 빌드할 때 운영 공개 API(`/api/v1/store`, `/workshops`, `/cases`, `/guides`)에서 받는다. 실패하면 빌드 실패 | CI (deploy.yml) |
| 없음 | `lib/demo.ts` 예시 데이터 | 로컬 개발 |

- 식물(블로그 글)은 아직 API가 없어 두 경우 모두 예시 데이터다 (ADR 0027 S-01을 만들면 바꾼다)
- 손님 브라우저는 API를 부르지 않는다 (견적 문의 접수만 예외). 관리 화면에서 내용을 바꾸면 **다시 빌드·배포해야** 사이트에 보인다
  (자동 재빌드는 ADR 0015, 아직 연결 전)
- 목록이 비어도 빌드되도록 상세 페이지에 자리표시 주소(`_`)를 하나 만들고, 빌드 후 지운다 (`scripts/build-hooks.mjs`)

## 구조
| 경로 | 내용 |
|---|---|
| `app/dohwa.css` | 프로토타입 `styles.css` 그대로 (클래스 이름을 바꾸지 말 것) |
| `app/site.css` | 이 저장소에서 더한 스타일 (준비 중 띠 등) |
| `app/layout.tsx` | 글꼴, 헤더·푸터·상담 창, noindex |
| `app/page.tsx` | 홈 (프로토타입 `home()`과 같은 마크업) |
| `app/not-found.tsx` | `out/404.html`. 배포 확인이 "찾으시는 페이지가 없어요" 문구를 검사한다 |
| `public/error.html` | 서버 장애(502~504) 때 CloudFront가 보여 주는 페이지. 서버 없이 열려야 해서 독립 HTML |
| `components/` | 프로토타입의 `header()`, `footer()`, `section()`, `plantCard()`… 를 옮긴 컴포넌트 |
| `lib/demo.ts` | 예시 데이터 (API 응답 형태). 페이지별로 빌드 시 API 조회로 바꾼다 |
| `public/assets/` | 프로토타입 예시 이미지. **출시 전에 실제 사진으로 교체** (일부는 실제 가게가 아닌 생성 이미지) |

## 출시 전 / 출시
- 기본은 **준비 중** 모드: 화면 아래 "사이트를 준비하고 있어요" 띠, `robots: noindex, nofollow`
- 출시할 때 빌드 환경 변수 `SITE_STAGE=live` (deploy.yml의 프론트엔드 빌드 단계)

## 옮긴 것과 남은 것
- [x] 공통 틀 (헤더, 휴대폰 메뉴, 푸터, 하단 상담 바, 상담 창, 검색 창, 스크롤 움직임)
- [x] 홈, 404
- [x] 식물 목록(목적·판매 중 필터)·상세, 클래스·상세, 진행 사례(기관 종류·페이지)·상세,
      관리 가이드(이름 검색)·상세, 오시는 길, 링크 모음
- [x] 견적 문의: **실제 API로 접수** (`POST /api/v1/inquiries`), 서버 필수 항목에 맞춤, 칸별 오류 표시, 첫 방문 경로 기록
- [ ] 빌드 시 API 조회 (`/api/v1/store`, `/workshops`, `/cases`, `/guides`, 블로그 식물)
- [ ] 관리 화면 (프로토타입 `#/admin`)

### 목록 필터와 정적 빌드
목록 페이지는 빌드할 때 **필터 없는 전체 목록**을 HTML로 만들고(검색엔진용), 브라우저에서 주소의
`?purpose=`, `?available=1`, `?type=`, `?page=`를 읽어 다시 그린다 (`components/*-browser.tsx`).
상세 페이지는 `generateStaticParams`로 항목마다 HTML을 만들고, 없는 주소는 404.
