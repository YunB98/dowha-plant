# frontend — 손님 사이트 (Next.js 정적 빌드)

디자인 원본은 사장님 쪽에서 만든 프로토타입이다 (`github.com/cd1070k987654321-beep/dohwa-frontend`, ADR 0028).
이 폴더는 그 디자인을 Next.js로 옮겨 빌드 시 HTML로 만들고 S3 + CloudFront로 배포한다 (ADR 0015, 0021).

## 실행
```bash
npm ci
npm run dev        # http://localhost:3000
npm run build      # out/ 에 정적 사이트 (index.html, 404.html, error.html, _next/…)
npm run typecheck
```

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
- [ ] 식물 목록·상세, 클래스, 진행 사례, 견적 문의, 관리 가이드, 오시는 길, 링크 모음
- [ ] 빌드 시 API 조회 (`/api/v1/store`, `/workshops`, `/cases`, `/guides`, 블로그 식물)
- [ ] 관리 화면 (프로토타입 `#/admin`)
