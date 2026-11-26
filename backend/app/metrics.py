"""비즈니스 지표 (docs/api-spec.md 3장). /metrics는 Nginx가 밖으로 내보내지 않는다."""

from prometheus_client import Counter

INQUIRIES_CREATED = Counter(
    "dowha_inquiries_created_total", "문의 접수 수", ["type", "source"]
)
INQUIRIES_SPAM = Counter("dowha_inquiries_spam_total", "허니팟에 걸린 문의 수")
NOTIFICATIONS_FAILED = Counter(
    "dowha_notifications_failed_total", "알림 실패 수", ["channel"]
)
