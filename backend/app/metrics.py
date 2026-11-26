"""비즈니스 지표 (docs/api-spec.md 3장). /metrics는 Nginx가 밖으로 내보내지 않는다."""

from prometheus_client import Counter

INQUIRIES_CREATED = Counter(
    "dowha_inquiries_created_total", "문의 접수 수", ["type", "source"]
)
INQUIRIES_SPAM = Counter("dowha_inquiries_spam_total", "허니팟에 걸린 문의 수")
NOTIFICATIONS_FAILED = Counter(
    "dowha_notifications_failed_total", "알림 실패 수", ["channel"]
)
QR_SCANS = Counter(
    "dowha_qr_scans_total", "QR 스캔 수 (guide: 가이드로, fallback: 목록으로, unknown: 없는 코드)", ["result"]
)
ADMIN_LOGINS = Counter("dowha_admin_logins_total", "관리자 로그인 시도 수", ["result"])
QR_SCAN_FAILED = Counter("dowha_qr_scan_record_failed_total", "QR 스캔 기록 실패 수 (리디렉션은 했음)")
SITE_REBUILD_REQUESTS = Counter("dowha_site_rebuild_requests_total", "공개 콘텐츠 변경으로 사이트 재빌드를 요청한 수")
UPLOADS_REJECTED = Counter("dowha_uploads_rejected_total", "올라온 파일을 연결하지 않고 거부한 수", ["reason"])
STORAGE_ERRORS = Counter("dowha_storage_errors_total", "S3·CloudFront 요청 실패 수", ["operation"])
