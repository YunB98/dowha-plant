# 0019. 외부 헬스체크는 UptimeRobot을 쓴다

- 상태: 채택
- 날짜: 2026-11-23

## 배경
서버가 한 대라 같은 EC2의 Prometheus·Grafana는 서버가 멈추면 알림을 보내지 못한다. 바깥에서 사이트를 확인하는 헬스체크가 필요하다 (아키텍처 문서).

## 검토한 대안
| 대안 | 문제 |
|---|---|
| Route 53 헬스체크 + CloudWatch 알람 + SNS | 알람과 SNS를 us-east-1에 만들어야 하는데 조직 SCP가 막는다 (ADR 0017). 헬스체크 비용도 든다 |
| **UptimeRobot (무료 플랜)** | 5분 간격 확인, 텔레그램 알림 연동 |

## 결정
UptimeRobot으로 아래를 확인하고, 장애 시 운영자 텔레그램으로 알린다.
- `https://dowha-plant.shop/` (정적 사이트, CloudFront·S3)
- `https://dowha-plant.shop/api/v1/health/ready` (백엔드와 DB)
- `https://dowha-plant.shop/q/` 경로의 리디렉션 (인쇄된 QR, ADR 0013)

## 결과
- 외부 서비스 계정 하나가 늘어난다. 로그인 정보는 비밀번호 관리자에 두고 2단계 인증을 켠다.
- 확인 간격이 5분이라 짧은 장애는 놓칠 수 있다. 가게 사이트 규모에서는 충분하다.
