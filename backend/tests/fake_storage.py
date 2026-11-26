"""테스트용 메모리 S3 (app.storage.Storage와 같은 인터페이스)."""

from dataclasses import dataclass, field

from app.storage import ObjectInfo, StorageError


@dataclass
class Obj:
    body: bytes
    content_type: str
    cache_control: str = ""


@dataclass
class FakeStorage:
    media_bucket: str = "media"
    site_bucket: str = "site"
    objects: dict[tuple[str, str], Obj] = field(default_factory=dict)
    invalidations: list[list[str]] = field(default_factory=list)
    fail: set[str] = field(default_factory=set)  # 실패시킬 동작 이름

    def _maybe_fail(self, op: str) -> None:
        if op in self.fail:
            raise StorageError(f"fake {op} failure")

    def upload(self, key: str, body: bytes, content_type: str) -> None:
        """브라우저가 presigned POST로 올린 것처럼 tmp에 넣는다."""
        self.objects[(self.media_bucket, key)] = Obj(body, content_type)

    def presign_post(self, key: str, content_type: str, max_size: int, expires_in: int) -> tuple[str, dict[str, str]]:
        self._maybe_fail("presign")
        return f"https://{self.media_bucket}.s3.example/", {
            "key": key, "Content-Type": content_type, "policy": f"max={max_size};exp={expires_in}", "x-amz-signature": "sig"
        }

    def head(self, bucket: str, key: str) -> ObjectInfo | None:
        self._maybe_fail("head")
        obj = self.objects.get((bucket, key))
        return ObjectInfo(len(obj.body), obj.content_type) if obj else None

    def read_start(self, bucket: str, key: str, length: int) -> bytes:
        return self.objects[(bucket, key)].body[:length]

    def copy(self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str,
             content_type: str, cache_control: str) -> None:
        self._maybe_fail("copy")
        src = self.objects[(src_bucket, src_key)]
        self.objects[(dst_bucket, dst_key)] = Obj(src.body, content_type, cache_control)

    def delete(self, bucket: str, key: str) -> None:
        self._maybe_fail("delete")
        self.objects.pop((bucket, key), None)

    def invalidate(self, paths: list[str]) -> str:
        self._maybe_fail("invalidate")
        self.invalidations.append(paths)
        return "I123"

    def keys(self, bucket: str | None = None) -> set[str]:
        return {k for b, k in self.objects if bucket is None or b == bucket}
