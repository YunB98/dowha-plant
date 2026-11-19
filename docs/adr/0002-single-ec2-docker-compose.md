# 0002. EC2 한 대 + Docker Compose 구성

- 상태: 채택
- 날짜: 2026-11-19

## 배경
세 가지 구성을 비교했다.

| 안 | 구성 | 월 비용 (추정) |
|---|---|---|
| A | S3 + CloudFront + API Gateway + Lambda + DynamoDB | 1천~3천 원 |
| B | S3 + CloudFront + EC2 한 대 (Docker Compose) | 1.5만~2.5만 원 |
| C | ECS Fargate + ALB + RDS | 7만 원 이상 |

## 결정
B안을 사용한다. EC2 t4g.small 한 대에서 Nginx, FastAPI, PostgreSQL, Prometheus, Grafana를 Docker Compose로 실행한다.

## 이유
- 가게 규모에 비해 C안은 과하다.
- A안은 저렴하지만 리눅스, 컨테이너, 서버 운영 경험을 보여주기 어렵다.
- B안은 비용을 낮게 유지하면서 컨테이너, 모니터링, 백업, 장애 복구를 모두 직접 다룰 수 있다.

## 결과
- 서버가 한 대라 장애에 약하다. 매일 DB 백업, EBS 스냅샷, 외부 헬스체크로 보완한다.
- 목표: RPO 24시간, RTO 1시간.
- C안은 트래픽이 늘었을 때의 확장 설계로만 문서에 남긴다.
