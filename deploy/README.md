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
| `origin-verify-secret`, `postgres-password`, `umami-db-password`, `umami-app-secret`, `grafana-admin-password` | Terraform (`infra/envs/prod`) |
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
