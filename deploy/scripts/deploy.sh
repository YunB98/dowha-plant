#!/bin/bash
# 서버(/opt/dowha)에서 root로 실행한다. 다시 실행해도 안전하다.
#   sudo /opt/dowha/scripts/deploy.sh <백엔드 이미지 태그(커밋 SHA)>
#
# 1. SSM에서 비밀값을 읽어 .env와 Alertmanager 설정을 만든다
# 2. 오리진 인증서를 받거나 갱신하고, 자동 갱신 타이머를 설치한다
# 3. ECR에 로그인해 이미지를 받고 컨테이너를 올린다
set -euo pipefail

TAG="${1:?사용법: deploy.sh <백엔드 이미지 태그>}"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REGION="ap-northeast-2"
PREFIX="/dowha-plant/prod"
ORIGIN_DOMAIN="origin.dowha-plant.shop"
export AWS_DEFAULT_REGION="$REGION"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
BACKEND_IMAGE="${REGISTRY}/dowha-plant-prod/backend:${TAG}"

cd "$APP_DIR"
umask 077

# --- 1. 비밀값 -------------------------------------------------------------
# 이름으로 직접 읽는다. 서버 역할은 ${PREFIX}/* 아래 값만 읽을 수 있고,
# get-parameters-by-path는 경로 자체(${PREFIX})에 대한 권한을 따로 요구하기 때문이다.
KEYS=(origin-verify-secret postgres-password umami-db-password umami-app-secret
      grafana-admin-password session-secret telegram-bot-token telegram-chat-id
      deploy/site-bucket deploy/media-bucket deploy/cloudfront-distribution-id)
NAMES=()
for key in "${KEYS[@]}"; do NAMES+=("${PREFIX}/${key}"); done

# get-parameters는 한 번에 10개까지만 받는다. 11개가 되자 배포가 멈춘 적이 있어(2026-11-26) 10개씩 나눠 읽는다.
BATCH=10
declare -A P
for ((i = 0; i < ${#NAMES[@]}; i += BATCH)); do
  batch=("${NAMES[@]:i:BATCH}")

  # 먼저 값 없이 확인한다. 권한 오류면 AWS CLI 오류가 그대로 보이고 여기서 멈춘다.
  missing="$(aws ssm get-parameters --names "${batch[@]}" --query 'InvalidParameters' --output text)"
  if [ -n "$missing" ]; then
    echo "SSM 파라미터가 없습니다 (deploy/README.md 참고): $missing" >&2
    exit 1
  fi

  while IFS=$'\t' read -r name value; do
    P["${name#"$PREFIX"/}"]="$value"
  done < <(aws ssm get-parameters --names "${batch[@]}" --with-decryption \
            --query 'Parameters[].[Name,Value]' --output text)
done

for key in "${KEYS[@]}"; do
  if [ -z "${P[$key]:-}" ]; then
    echo "SSM 파라미터 ${PREFIX}/${key} 를 읽지 못했습니다" >&2
    exit 1
  fi
done

# 작은따옴표로 감싸면 Compose가 값 안의 $를 변수로 해석하지 않는다.
cat > .env <<EOF
ORIGIN_DOMAIN='${ORIGIN_DOMAIN}'
ORIGIN_VERIFY_SECRET='${P[origin-verify-secret]}'
POSTGRES_PASSWORD='${P[postgres-password]}'
UMAMI_DB_PASSWORD='${P[umami-db-password]}'
UMAMI_APP_SECRET='${P[umami-app-secret]}'
GRAFANA_ADMIN_PASSWORD='${P[grafana-admin-password]}'
SESSION_SECRET='${P[session-secret]}'
SITE_BUCKET='${P[deploy/site-bucket]}'
MEDIA_BUCKET='${P[deploy/media-bucket]}'
CLOUDFRONT_DISTRIBUTION_ID='${P[deploy/cloudfront-distribution-id]}'
TELEGRAM_BOT_TOKEN='${P[telegram-bot-token]}'
TELEGRAM_CHAT_ID='${P[telegram-chat-id]}'
BACKEND_IMAGE='${BACKEND_IMAGE}'
EOF

# Alertmanager 컨테이너는 nobody(65534)로 실행되므로 읽을 수 있게 소유자를 바꾼다.
mkdir -p monitoring/alertmanager/rendered
sed "s/__TELEGRAM_CHAT_ID__/${P[telegram-chat-id]}/" \
  monitoring/alertmanager/alertmanager.yml.tmpl > monitoring/alertmanager/rendered/alertmanager.yml
printf '%s' "${P[telegram-bot-token]}" > monitoring/alertmanager/rendered/telegram_bot_token
chown -R 65534:65534 monitoring/alertmanager/rendered
umask 022

# --- 2. 오리진 인증서 -------------------------------------------------------
"$APP_DIR/scripts/renew-cert.sh"

install -m 644 systemd/dowha-cert-renew.service /etc/systemd/system/
install -m 644 systemd/dowha-cert-renew.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now dowha-cert-renew.timer

# --- 3. 설정 검사와 변경 표시 --------------------------------------------------
# 배포는 설정 폴더를 지우고 새로 복사한다. 실행 중인 컨테이너의 bind mount는 지워진 옛 폴더를 계속 가리켜서
# reload나 SIGHUP으로는 새 설정을 읽지 못한다 (2026-11-26: 요청 수 제한·api 수집·새 경보가 적용되지 않았다).
# 설정 해시를 컨테이너 라벨로 넘겨, 바뀐 서비스만 compose가 다시 만들게 한다.
config_hash() { find "$@" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-16; }
{
  echo "NGINX_CONFIG_HASH=$(config_hash nginx)"
  echo "PROMETHEUS_CONFIG_HASH=$(config_hash monitoring/prometheus)"
  echo "ALERTMANAGER_CONFIG_HASH=$(config_hash monitoring/alertmanager/rendered)"
} >> .env

# 다시 만들기 전에 새 설정을 임시 컨테이너로 검사한다. 틀리면 여기서 멈추고 실행 중인 서비스는 그대로다.
docker compose run --rm --no-deps -T nginx nginx -t < /dev/null
docker compose run --rm --no-deps -T --entrypoint promtool prometheus \
  check config /etc/prometheus/prometheus.yml < /dev/null
docker compose run --rm --no-deps -T --entrypoint amtool alertmanager \
  check-config /etc/alertmanager/alertmanager.yml < /dev/null

# --- 4. 컨테이너 ------------------------------------------------------------
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker compose pull --quiet
docker compose up -d --remove-orphans

docker compose ps

# --- 5. 정기 작업 -----------------------------------------------------------
# 처리 끝난 문의의 개인정보 삭제 (매일 03:30 KST, backend/app/purge.py). api 컨테이너가 뜬 뒤에 켠다
install -m 644 systemd/dowha-pii-purge.service /etc/systemd/system/
install -m 644 systemd/dowha-pii-purge.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now dowha-pii-purge.timer

# 블로그 새 글 가져오기 (매시간, backend/app/blog_import.py, ADR 0027)
install -m 644 systemd/dowha-blog-import.service /etc/systemd/system/
install -m 644 systemd/dowha-blog-import.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now dowha-blog-import.timer
