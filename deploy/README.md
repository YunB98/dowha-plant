# deploy — prod 서버 구성

EC2(t4g.micro) 한 대에서 Docker Compose로 실행한다. 이 폴더 내용이 서버의 `/opt/dowha`에 그대로 놓인다.

| 서비스 | 메모리 제한 | 외부 노출 |
|---|---|---|
| nginx | 32MB | 443 (CloudFront만, 보안 그룹) |
| api (FastAPI) | 160MB | Nginx 뒤 `/api/*`, `/q/*` |
| postgres | 192MB | 없음 |
| umami | 256MB | `/umami/script.js`, `/umami/api/send`만. 관리 화면 `127.0.0.1:3000` |
| prometheus | 64MB | `127.0.0.1:9090` |
| alertmanager | 32MB | 없음 (텔레그램으로 보냄) |
| node-exporter | 32MB | 없음 |
| grafana (`dashboard` 프로필) | 128MB | `127.0.0.1:3001`, 필요할 때만 |

상시 합계 768MB + OS 약 150MB (ADR 0022).

## 비밀값 (SSM Parameter Store, `/dowha-plant/prod/`)
| 이름 | 만드는 곳 |
|---|---|
| `origin-verify-secret`, `postgres-password`, `umami-db-password`, `umami-app-secret`, `grafana-admin-password`, `session-secret` | Terraform (`infra/envs/prod`) |
| `telegram-bot-token`, `telegram-chat-id` | **직접** (외부 발급 값이라 Terraform 상태에 두지 않음) |

텔레그램 값 넣기 (봇은 @BotFather에서 만들고, 채팅 ID는 봇에게 말을 건 뒤 `getUpdates`로 확인):
```bash
aws ssm put-parameter --name /dowha-plant/prod/telegram-bot-token --type SecureString --value '<토큰>'
aws ssm put-parameter --name /dowha-plant/prod/telegram-chat-id   --type String       --value '<채팅 ID>'
```

## 배포
```bash
sudo /opt/dowha/scripts/deploy.sh <백엔드 이미지 태그>
```
1. SSM 값으로 `.env`, Alertmanager 설정을 만든다 (권한 600, 저장소에 올리지 않음)
2. 오리진 인증서를 Let's Encrypt DNS-01로 받거나 갱신하고, 하루 두 번 갱신 타이머를 설치한다
   (처음 실행하면 Let's Encrypt 가입 약관에 동의한 것으로 처리된다)
3. ECR 로그인 → `docker compose pull` → `up -d`

## 관리자 계정 (ADR 0025)
계정은 API로 만들 수 없고, 서버 안에서 명령으로만 만든다. 비밀번호는 화면에 보이지 않게 직접 입력한다.
명령 인자로 넘기지 말 것 (셸 기록과 SSM 실행 기록에 남는다).
```bash
aws ssm start-session --target <인스턴스 ID>          # 대화형 셸 (send-command가 아니라)
cd /opt/dowha
sudo docker compose exec api python -m app.admin_cli create-user owner --role owner
sudo docker compose exec api python -m app.admin_cli list
```
| 상황 | 명령 |
|---|---|
| 비밀번호를 잊었다 | `set-password owner` (모든 기기 로그아웃도 같이 된다) |
| 휴대폰을 잃어버렸다, 로그인 실패 경보(`AdminLoginFailures`)가 왔다 | `logout-all owner` 후 `set-password owner` |
| 모든 계정을 한 번에 로그아웃 | SSM `session-secret` 값을 바꾸고 다시 배포 |

## 정기 작업 (systemd 타이머, deploy.sh가 설치)
| 타이머 | 시각 | 하는 일 | 확인 |
|---|---|---|---|
| `dowha-cert-renew` | 하루 두 번 | 오리진 인증서 갱신 | `journalctl -u dowha-cert-renew` |
| `dowha-pii-purge` | 매일 03:30 KST | 보관 기간이 지난 문의의 개인정보 삭제 | `journalctl -u dowha-pii-purge` |
| `dowha-blog-import` | 매시간 | 네이버 블로그 새 글 가져오기 (대표 사진은 S3 사본) | `journalctl -u dowha-blog-import` |

```bash
systemctl list-timers 'dowha-*'                                       # 다음 실행 시각
sudo docker compose exec -T api python -m app.purge --dry-run        # 지금 지울 대상 수
sudo docker compose exec -T api python -m app.blog_import            # 블로그 새 글 지금 가져오기
```
경보 `PiiPurgeOverdue`가 오면: 타이머가 켜져 있는지(`systemctl status dowha-pii-purge.timer`), 마지막 실행 로그를 본다.

## 운영자 접속 (SSM 포트 포워딩)
```bash
aws ssm start-session --target <인스턴스 ID> \
  --document-name AWS-StartPortForwardingSession --parameters 'portNumber=3000,localPortNumber=3000'
```
3000 Umami, 9090 Prometheus, 3001 Grafana (`docker compose --profile dashboard up -d grafana` 후).

## CI 배포 (`.github/workflows/deploy.yml`, ADR 0023)
`backend/`, `deploy/`가 바뀐 커밋이 main에 들어오면 production 승인 후 자동으로 위 배포를 실행한다.
처음 한 번만 필요한 준비:
1. prod 스택 apply로 배포 역할 생성 → `terraform output github_deploy_role_arn`
2. GitHub `production` 환경 변수 `AWS_DEPLOY_ROLE_ARN`에 그 값을 넣는다
3. 텔레그램 SSM 파라미터 두 개를 넣는다 (위 "비밀값")
