"""S3·CloudFront 접근 (ADR 0026).

boto3 대신 botocore의 서명(SigV4)과 자격 증명 체인만 쓰고, 요청은 httpx로 보낸다.
boto3는 서비스 정의(JSON)를 메모리에 올려서 api 컨테이너(160MB)에서 약 45MB를 더 쓰는데, 이 방식은 약 12MB다.
보안에 민감한 부분(서명 계산, IMDSv2 자격 증명 갱신)은 botocore 코드를 그대로 쓴다.

쓰는 요청은 다섯 가지뿐이다.
- presigned POST: 브라우저가 S3로 직접 올린다 (형식·크기를 정책으로 강제)
- HEAD / 앞부분 GET: 올라온 파일의 크기·형식·실제 내용(매직 바이트) 확인
- PUT + x-amz-copy-source: uploads/tmp/ → images/ 이동 (복사 후 삭제)
- DELETE
- CloudFront CreateInvalidation (소개서 교체)

테스트는 이 인터페이스를 메모리 구현(tests/fake_storage.py)으로 바꿔 끼운다.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Protocol
from urllib.parse import quote
from uuid import uuid4

import httpx
from botocore.auth import S3SigV4Auth, S3SigV4PostAuth, SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials, create_credential_resolver
from botocore.session import get_session
from fastapi import HTTPException

from app.config import get_settings

log = logging.getLogger("dowha.storage")


class StorageError(Exception):
    """AWS 요청 실패. API는 503으로 응답한다 (상세는 로그에만)."""


@dataclass(frozen=True)
class ObjectInfo:
    size: int
    content_type: str


class Storage(Protocol):
    media_bucket: str
    site_bucket: str

    def presign_post(self, key: str, content_type: str, max_size: int, expires_in: int) -> tuple[str, dict[str, str]]: ...
    def head(self, bucket: str, key: str) -> ObjectInfo | None: ...
    def read_start(self, bucket: str, key: str, length: int) -> bytes: ...
    def copy(self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str,
             content_type: str, cache_control: str) -> None: ...
    def delete(self, bucket: str, key: str) -> None: ...
    def invalidate(self, paths: list[str]) -> str: ...


class S3Storage:
    def __init__(self, region: str, media_bucket: str, site_bucket: str, distribution_id: str) -> None:
        self.region = region
        self.media_bucket = media_bucket
        self.site_bucket = site_bucket
        self.distribution_id = distribution_id
        # 환경 변수 → 프로필 → 컨테이너 → EC2 인스턴스 역할(IMDSv2) 순서. 만료 전에 알아서 갱신한다
        self._credentials = create_credential_resolver(get_session()).load_credentials()
        self._http = httpx.Client(timeout=httpx.Timeout(10.0, read=30.0))

    # ---------- 내부 ----------

    def _creds(self) -> Credentials:
        if self._credentials is None:
            raise StorageError("AWS 자격 증명을 찾지 못했습니다")
        return self._credentials.get_frozen_credentials()

    def _url(self, bucket: str, key: str) -> str:
        return f"https://{bucket}.s3.{self.region}.amazonaws.com/{quote(key)}"

    def _send(self, method: str, url: str, *, service: str = "s3", region: str | None = None,
              headers: dict[str, str] | None = None, body: bytes = b"") -> httpx.Response:
        request = AWSRequest(method=method, url=url, headers=headers or {}, data=body)
        auth_class = S3SigV4Auth if service == "s3" else SigV4Auth
        auth_class(self._creds(), service, region or self.region).add_auth(request)
        try:
            return self._http.request(method, url, headers=dict(request.headers.items()), content=body)
        except httpx.HTTPError as e:
            raise StorageError(f"{method} {url.split('?')[0]}: {e}") from e

    @staticmethod
    def _check(res: httpx.Response, *ok: int) -> None:
        # CopyObject는 200이면서 본문에 <Error>를 담아 실패를 알리기도 한다
        if res.status_code not in ok or b"<Error>" in res.content[:512]:
            raise StorageError(f"{res.request.method} {res.request.url.path} → {res.status_code} {res.text[:300]}")

    # ---------- 인터페이스 ----------

    def presign_post(self, key: str, content_type: str, max_size: int, expires_in: int) -> tuple[str, dict[str, str]]:
        expires = datetime.now(UTC) + timedelta(seconds=expires_in)
        request = AWSRequest(method="POST", url=f"https://{self.media_bucket}.s3.{self.region}.amazonaws.com/")
        request.context["s3-presign-post-fields"] = {"key": key, "Content-Type": content_type}
        request.context["s3-presign-post-policy"] = {
            "expiration": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "conditions": [
                {"bucket": self.media_bucket},
                {"key": key},  # 정해 준 키 하나에만 올릴 수 있다
                {"Content-Type": content_type},
                ["content-length-range", 1, max_size],
            ],
        }
        S3SigV4PostAuth(self._creds(), "s3", self.region).add_auth(request)
        return request.url, dict(request.context["s3-presign-post-fields"])

    def head(self, bucket: str, key: str) -> ObjectInfo | None:
        res = self._send("HEAD", self._url(bucket, key))
        if res.status_code == 404:
            return None
        self._check(res, 200)
        return ObjectInfo(size=int(res.headers.get("content-length", 0)), content_type=res.headers.get("content-type", ""))

    def read_start(self, bucket: str, key: str, length: int) -> bytes:
        res = self._send("GET", self._url(bucket, key), headers={"Range": f"bytes=0-{length - 1}"})
        self._check(res, 200, 206)
        return res.content[:length]

    def copy(self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str,
             content_type: str, cache_control: str) -> None:
        res = self._send("PUT", self._url(dst_bucket, dst_key), headers={
            "x-amz-copy-source": quote(f"/{src_bucket}/{src_key}"),
            "x-amz-metadata-directive": "REPLACE",
            "Content-Type": content_type,
            "Cache-Control": cache_control,
        })
        self._check(res, 200)

    def delete(self, bucket: str, key: str) -> None:
        res = self._send("DELETE", self._url(bucket, key))
        self._check(res, 204, 200)

    def invalidate(self, paths: list[str]) -> str:
        items = "".join(f"<Path>{p}</Path>" for p in paths)
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<InvalidationBatch xmlns="http://cloudfront.amazonaws.com/doc/2020-05-31/">'
            f"<Paths><Quantity>{len(paths)}</Quantity><Items>{items}</Items></Paths>"
            f"<CallerReference>{uuid4().hex}</CallerReference></InvalidationBatch>"
        ).encode()
        url = f"https://cloudfront.amazonaws.com/2020-05-31/distribution/{self.distribution_id}/invalidation"
        # CloudFront는 전역 서비스라 서명 지역이 us-east-1이다
        res = self._send("POST", url, service="cloudfront", region="us-east-1",
                         headers={"Content-Type": "application/xml"}, body=body)
        self._check(res, 201)
        return res.text.split("<Id>", 1)[1].split("</Id>", 1)[0] if "<Id>" in res.text else ""


@lru_cache
def _s3() -> S3Storage:
    s = get_settings()
    return S3Storage(s.aws_region, s.media_bucket, s.site_bucket, s.cloudfront_distribution_id)


def get_storage() -> Storage:
    """FastAPI 의존성. 버킷 설정이 없으면(로컬) 업로드 API는 503."""
    s = get_settings()
    if not (s.media_bucket and s.site_bucket and s.cloudfront_distribution_id):
        raise HTTPException(status_code=503, detail="사진 저장소가 설정되지 않았어요.")
    return _s3()


def new_key(prefix: str, ext: str) -> str:
    """추측할 수 없는 이름. 같은 이름을 다시 쓰지 않으므로 CloudFront 캐시를 지울 필요가 없다."""
    return f"{prefix.rstrip('/')}/{uuid4().hex}.{ext}"
