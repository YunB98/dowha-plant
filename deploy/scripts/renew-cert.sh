#!/bin/bash
# 오리진 인증서(origin.dowha-plant.shop)를 Let's Encrypt DNS-01로 받거나 갱신한다.
# 80번 포트를 열지 않기 위해 HTTP-01 대신 Route 53 TXT 레코드로 인증한다 (ADR 0021).
# 서버 IAM 역할은 _acme-challenge.origin.dowha-plant.shop 레코드만 바꿀 수 있다.
# 만료 30일 전이 아니면 아무것도 하지 않는다. 타이머가 하루 두 번 실행한다.
set -euo pipefail

ORIGIN_DOMAIN="origin.dowha-plant.shop"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CERT="/etc/letsencrypt/live/${ORIGIN_DOMAIN}/fullchain.pem"
before="$(sha256sum "$CERT" 2>/dev/null || true)"

# 이메일 없이 등록한다 (만료 알림은 Prometheus·UptimeRobot이 대신한다).
docker run --rm \
  -v /etc/letsencrypt:/etc/letsencrypt \
  -v /var/lib/letsencrypt:/var/lib/letsencrypt \
  certbot/dns-route53:v4.1.1 \
  certonly --dns-route53 -d "$ORIGIN_DOMAIN" \
  --non-interactive --agree-tos --register-unsafely-without-email \
  --keep-until-expiring --key-type ecdsa

after="$(sha256sum "$CERT")"
if [ "$before" != "$after" ] && docker compose -f "$APP_DIR/compose.yaml" ps --status running nginx 2>/dev/null | grep -q nginx; then
  docker compose -f "$APP_DIR/compose.yaml" exec -T nginx nginx -s reload
  echo "인증서 갱신, nginx reload"
fi
