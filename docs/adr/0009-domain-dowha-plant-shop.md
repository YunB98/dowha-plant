# 0009. dowha-plant.shop 도메인 사용

- 상태: 채택
- 날짜: 2026-11-19
- 대체: ADR 0008

## 결정
- 도메인: `dowha-plant.shop` (가비아에서 등록 완료)
- 네임서버를 Route 53 호스팅 영역으로 위임한다.

## 이유
- `.kr` 대신 실제로 등록 가능하고 가게 성격(판매)에 맞는 `.shop`을 선택했다.

## 서브도메인 계획
| 주소 | 용도 |
|---|---|
| `dowha-plant.shop`, `www.dowha-plant.shop` | 사이트 (CloudFront) |
| `origin.dowha-plant.shop` | CloudFront → EC2 연결용 (Let's Encrypt 인증서) |
| `staging.dowha-plant.shop` | staging 환경 (필요할 때만) |

## 주의
- `.shop`은 첫해 할인가와 갱신 가격 차이가 클 수 있다. 갱신 가격을 확인하고 자동 갱신을 켜둔다.
- 도메인 등록자 명의와 가비아 계정 소유자를 기록해두고, 장기적으로 사장님 명의로 옮기는 것을 검토한다.
