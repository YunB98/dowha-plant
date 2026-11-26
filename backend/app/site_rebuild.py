"""공개 콘텐츠가 바뀌었을 때 정적 사이트 재빌드 요청 (ADR 0015).

지금은 기록만 한다. 5단계(프론트엔드)에서 사이트 빌드 워크플로를 만들 때
GitHub repository_dispatch(content-changed) 요청을 여기에 붙인다.
콘텐츠 관리 API는 공개 내용이 바뀌는 모든 곳에서 이 함수를 부른다.
"""

import logging

from app.metrics import SITE_REBUILD_REQUESTS

log = logging.getLogger("dowha.site")


def request_rebuild(reason: str) -> None:
    SITE_REBUILD_REQUESTS.inc()
    log.info("site rebuild requested: %s", reason)
