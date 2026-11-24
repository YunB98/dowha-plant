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
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
BACKEND_IMAGE="${REGISTRY}/dowha-plant-prod/backend:${TAG}"

cd "$APP_DIR"
umask 077

# --- 1. 비밀값 -------------------------------------------------------------
declare -A P
while IFS=$'\t' read -r name value; do
  P["${name#"$PREFIX"/}"]="$value"
done < <(aws ssm get-parameters-by-path --region "$REGION" --path "$PREFIX" \
          --recursive --with-decryption --query 'Parameters[].[Name,Value]' --output text)

require() {
  for key in "$@"; do
    if [ -z "${P[$key]:-}" ]; then
      echo "SSM 파라미터 ${PREFIX}/${key} 가 없습니다 (deploy/README.md 참고)" >&2
      exit 1
    fi
  done
}
require origin-verify-secret postgres-password umami-db-password umami-app-secret \
        grafana-admin-password telegram-bot-token telegram-chat-id

# 작은따옴표로 감싸면 Compose가 값 안의 $를 변수로 해석하지 않는다.
cat > .env <<EOF
ORIGIN_DOMAIN='${ORIGIN_DOMAIN}'
ORIGIN_VERIFY_SECRET='${P[origin-verify-secret]}'
POSTGRES_PASSWORD='${P[postgres-password]}'
UMAMI_DB_PASSWORD='${P[umami-db-password]}'
UMAMI_APP_SECRET='${P[umami-app-secret]}'
GRAFANA_ADMIN_PASSWORD='${P[grafana-admin-password]}'
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

# --- 3. 컨테이너 ------------------------------------------------------------
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker compose pull --quiet
docker compose up -d --remove-orphans
docker compose ps
