# 0022. 서버를 t4g.micro로 낮춰 월 20달러 이내로 운영한다

- 상태: 채택
- 날짜: 2026-11-23
- 대체: ADR 0021의 인스턴스 크기와 비용 부분

## 배경
ADR 0021의 t4g.small 구성은 월 약 21~23달러로, 목표(월 20달러 이내)와 조직 예산 차단 SCP(월 20달러, ADR 0017)를 넘는다.
트래픽은 하루 수십~수백 방문 수준으로 예상된다.

## 결정
| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| 인스턴스 | t4g.small (2GB) | **t4g.micro (1GB)** |
| 스왑 | 1GB | **2GB** |
| CPU 크레딧 | unlimited (기본값) | **standard** |

`standard` 크레딧: CPU를 오래 많이 쓰면 기본 성능(vCPU당 10%)으로 느려질 뿐 추가 요금이 붙지 않는다. 이미지 빌드는 CI에서 하므로 서버 CPU 사용량은 낮다.

## 비용 (서울, 온디맨드, AWS 가격표 기준)
| 항목 | 월 |
|---|---|
| EC2 t4g.micro (0.0104달러/시간) | 약 7.6달러 |
| 공인 IPv4 (0.005달러/시간) | 약 3.7달러 |
| EBS gp3 20GB + 스냅샷 | 약 2.3달러 |
| Route 53 호스팅 영역 | 0.5달러 |
| CloudFront, S3, ECR, SSM (소규모) | 약 0~1달러 |
| **합계** | **약 14~15달러** |

100달러 크레딧으로 약 6~7개월 운영할 수 있다.

## 메모리 예산 (1GB + 스왑 2GB)
모든 컨테이너에 Docker Compose `mem_limit`을 건다. 한 컨테이너가 메모리를 다 써서 서버 전체가 멈추는 것을 막는다.

| 구성 | 메모리 제한 | 설정 |
|---|---|---|
| OS, Docker | 약 150MB | |
| Nginx | 32MB | |
| FastAPI | 160MB | uvicorn 워커 1개 |
| PostgreSQL | 192MB | `shared_buffers=48MB`, `max_connections=20`. 앱과 Umami가 같은 서버를 쓰고 데이터베이스만 나눈다 |
| Umami | 224MB | 방문 분석 (ADR 0014 유지) |
| Prometheus | 96MB | 수집 주기 60초, 보관 7일 |
| Alertmanager | 32MB | 장애 알림 → 텔레그램 |
| node-exporter | 32MB | |
| **상시 실행 소계** | **약 920MB** | |
| Grafana | 128MB | **필요할 때만 실행** (아래) |

### Umami를 유지하는 대신 Grafana를 필요할 때만 켠다
- 방문 분석 도구로 더 가벼운 GoatCounter(약 30MB)도 검토했지만, 화면이 보기 좋은 Umami를 유지하기로 했다.
- 그 대신 Grafana를 상시 실행에서 뺀다. Docker Compose 프로필(`dashboard`)로 두고, 대시보드를 볼 때만 SSM 접속 후 켠다.
  ```bash
  docker compose --profile dashboard up -d grafana    # 볼 때
  docker compose --profile dashboard stop grafana     # 다 보면
  ```
- **알림은 Grafana가 아니라 Alertmanager가 보낸다.** 그래서 Grafana가 꺼져 있어도 장애 알림은 계속 온다. 알림 규칙은 Prometheus 규칙 파일로 코드에 둔다.
- 상시 메모리가 1GB에 가까우므로 스왑(2GB)이 일부 쓰이는 것은 정상이다. 아래 기준을 넘으면 서버를 올린다.

## 다시 올리는 기준
아래 중 하나가 1주일 이상 계속되면 `instance_type`을 t4g.small로 바꾼다 (변수 하나만 바꾸면 되고, 서버가 잠깐 재시작된다).
- 스왑 사용량이 500MB를 넘는 상태가 지속됨
- 메모리 부족으로 컨테이너가 종료(OOM)됨
- API 응답 시간 p95가 1초를 넘음
