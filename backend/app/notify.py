"""사장님 알림 (텔레그램).

- 응답을 보낸 뒤 백그라운드에서 보낸다. 실패해도 문의 저장은 그대로이고, 로그와 지표에만 남긴다.
- 알림에는 개인정보(이름, 연락처, 이메일)를 넣지 않는다. 텔레그램 서버에 남기 때문이다.
  자세한 내용은 관리 화면에서 본다.
"""

import logging

import httpx

from app.config import get_settings
from app.metrics import NOTIFICATIONS_FAILED

log = logging.getLogger("dowha.notify")

TYPE_LABELS = {
    "outreach": "출강",
    "group_visit": "매장 단체 수업",
    "corporate_order": "기업 대량 주문",
    "other": "기타",
}


def inquiry_message(inquiry_id: int, type_: str, organization_name: str, people_count: int,
                    preferred_schedule: str, source: str) -> str:
    return (
        f"🌱 새 문의 #{inquiry_id} ({TYPE_LABELS.get(type_, type_)})\n"
        f"기관: {organization_name}\n"
        f"인원: {people_count}명\n"
        f"희망 일정: {preferred_schedule}\n"
        f"유입: {source}\n"
        "연락처는 관리 화면에서 확인해주세요."
    )


def send_telegram(text: str) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        log.info("telegram not configured, skip")
        return
    try:
        res = httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": settings.telegram_chat_id, "text": text},
            timeout=10,
        )
        res.raise_for_status()
    except httpx.HTTPError as exc:
        NOTIFICATIONS_FAILED.labels(channel="telegram").inc()
        # 토큰이 URL에 들어 있으므로 예외 메시지(URL 포함)를 그대로 남기지 않는다
        status = getattr(getattr(exc, "response", None), "status_code", None)
        log.warning("telegram notify failed: %s status=%s", type(exc).__name__, status)
