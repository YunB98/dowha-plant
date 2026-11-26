"""사진·소개서 업로드 (docs/api-spec.md 2장 "사진 업로드", ADR 0026).

1. POST /admin/uploads/presign      → 브라우저가 S3 uploads/tmp/에 직접 올릴 주소 (5분, 형식·크기는 정책으로 강제)
2. 브라우저 → S3
3. POST /admin/{대상}/{id}/images    → 서버가 올라온 파일을 확인하고 images/{대상}/{id}/로 옮긴 뒤 연결

올라온 파일은 믿지 않는다. 연결하기 전에 S3에서 크기·형식을 다시 보고, 앞부분(매직 바이트)이 정말
JPEG/PNG/WebP/PDF인지 확인한다. 확인을 통과하지 못한 파일은 연결하지 않고 tmp에 둔다(1일 뒤 자동 삭제).

- HEIC는 받지 않는다. 크롬 등 대부분 브라우저가 표시하지 못한다 (아이폰은 업로드할 때 JPEG로 바꿔 준다)
- 큰 사진 줄이기는 관리 화면(브라우저)에서 한다. 서버에서 줄이면 api 메모리(160MB)를 넘을 수 있다
- 사진 이름은 매번 새로 만들어서(uuid) CloudFront 캐시를 1년 둔다
- DB와 S3는 함께 되돌릴 수 없다. 순서를 "S3 복사 → DB 저장 → tmp 삭제"로 하고,
  DB 저장이 실패하면 복사본을 지운다. S3 삭제가 실패해도 DB가 기준이며, 남은 파일은 로그와 지표로 남긴다
"""

import logging
import re
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.auth import current_admin
from app.db import get_db
from app.metrics import STORAGE_ERRORS, UPLOADS_REJECTED
from app.models import AdminUser, Base, Case, Image, PlantGuide, Setting, ShowcaseItem, Workshop
from app.public import public_url
from app.site_rebuild import request_rebuild
from app.storage import Storage, StorageError, get_storage, new_key

# 로그인 확인을 라우터에 걸어 가장 먼저 실행한다 (저장소 설정 확인보다 먼저: 로그인 전에는 무조건 401)
router = APIRouter(prefix="/api/v1/admin", tags=["admin-uploads"], dependencies=[Depends(current_admin)])
log = logging.getLogger("dowha.admin")

TMP_PREFIX = "uploads/tmp/"
TMP_KEY_RE = re.compile(r"^uploads/tmp/[0-9a-f]{32}\.(jpg|png|webp|pdf)$")
PRESIGN_SECONDS = 300
MAX_IMAGES_PER_ITEM = 20
IMAGE_CACHE = "public, max-age=31536000, immutable"
BROCHURE_KEY = "files/brochure.pdf"
BROCHURE_CACHE = "public, max-age=300"


@dataclass(frozen=True)
class FileKind:
    ext: str
    max_size: int
    magic: tuple[bytes, ...]  # 파일 앞부분

    def matches(self, head: bytes) -> bool:
        if self.ext == "webp":
            return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
        return any(head.startswith(m) for m in self.magic)


MB = 1024 * 1024
KINDS: dict[str, dict[str, FileKind]] = {
    "image": {
        "image/jpeg": FileKind("jpg", 10 * MB, (b"\xff\xd8\xff",)),
        "image/png": FileKind("png", 10 * MB, (b"\x89PNG\r\n\x1a\n",)),
        "image/webp": FileKind("webp", 10 * MB, ()),
    },
    "brochure": {"application/pdf": FileKind("pdf", 20 * MB, (b"%PDF-",))},
}


# ---------- 사진 주인 ----------

Target = Literal["workshops", "cases", "showcase", "guides"]


@dataclass(frozen=True)
class Owner:
    model: type[Base]
    column: InstrumentedAttribute[int | None]


OWNERS: dict[str, Owner] = {
    "workshops": Owner(Workshop, Image.workshop_id),
    "cases": Owner(Case, Image.case_id),
    "showcase": Owner(ShowcaseItem, Image.showcase_item_id),
    "guides": Owner(PlantGuide, Image.plant_guide_id),
}


def owner_of(image: Image) -> tuple[str, int]:
    for target, owner in OWNERS.items():
        owner_id = getattr(image, owner.column.key)
        if owner_id is not None:
            return target, owner_id
    raise AssertionError("사진에 주인이 없다 (DB CHECK exactly_one_owner 위반)")


def delete_files(storage: Storage | None, keys: list[str]) -> None:
    """DB에서 지운 사진의 파일을 지운다. 실패해도 요청은 성공 (버킷 버전 관리로 30일 뒤 정리)."""
    if storage is None:
        return
    for key in keys:
        try:
            storage.delete(storage.media_bucket, key)
        except StorageError:
            STORAGE_ERRORS.labels(operation="delete").inc()
            log.exception("image file delete failed: %s", key)


# ---------- 형식 ----------


class PresignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: Literal["image", "brochure"]
    content_type: str = Field(max_length=100)
    size: int = Field(ge=1)


class PresignOut(BaseModel):
    upload_url: str
    fields: dict[str, str]
    s3_key: str
    expires_in: int


class AttachIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    s3_key: str = Field(max_length=100)
    alt_text: str = Field("", max_length=200)


class ImageOut(BaseModel):
    id: int
    image_url: str
    alt_text: str
    sort_order: int


class OrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_ids: list[int] = Field(max_length=MAX_IMAGES_PER_ITEM)


class AltIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    alt_text: str = Field(max_length=200)


def image_out(image: Image) -> ImageOut:
    return ImageOut(id=image.id, image_url=public_url(image.s3_key), alt_text=image.alt_text, sort_order=image.sort_order)


def images_of(db: Session, target: str, owner_id: int) -> list[Image]:
    column = OWNERS[target].column
    return list(db.scalars(select(Image).where(column == owner_id).order_by(Image.sort_order, Image.id)))


# ---------- 업로드 주소 ----------


def reject(reason: str, message: str) -> HTTPException:
    UPLOADS_REJECTED.labels(reason=reason).inc()
    return HTTPException(status_code=422, detail=message)


@router.post("/uploads/presign")
def presign(body: PresignIn, storage: Storage = Depends(get_storage), _: AdminUser = Depends(current_admin)) -> PresignOut:
    kind = KINDS[body.purpose].get(body.content_type)
    if kind is None:
        allowed = ", ".join(KINDS[body.purpose])
        raise HTTPException(status_code=422, detail=f"올릴 수 있는 형식: {allowed}")
    if body.size > kind.max_size:
        raise HTTPException(status_code=422, detail=f"{kind.max_size // MB}MB 이하만 올릴 수 있어요.")
    key = new_key(TMP_PREFIX, kind.ext)
    try:
        url, fields = storage.presign_post(key, body.content_type, kind.max_size, PRESIGN_SECONDS)
    except StorageError as e:
        STORAGE_ERRORS.labels(operation="presign").inc()
        log.exception("presign failed")
        raise HTTPException(status_code=503) from e
    return PresignOut(upload_url=url, fields=fields, s3_key=key, expires_in=PRESIGN_SECONDS)


def verify_upload(storage: Storage, key: str, purpose: str) -> FileKind:
    """올라온 파일이 약속한 형식·크기인지 S3에서 직접 확인한다."""
    if not TMP_KEY_RE.fullmatch(key):
        raise reject("bad_key", "업로드 주소 발급으로 받은 s3_key를 보내주세요.")
    try:
        info = storage.head(storage.media_bucket, key)
        if info is None:
            raise reject("missing", "업로드한 파일이 없어요. 다시 올려주세요.")
        kind = KINDS[purpose].get(info.content_type)
        if kind is None or not key.endswith("." + kind.ext):
            raise reject("type", "파일 형식이 맞지 않아요.")
        if info.size > kind.max_size:
            raise reject("size", f"{kind.max_size // MB}MB 이하만 올릴 수 있어요.")
        if not kind.matches(storage.read_start(storage.media_bucket, key, 16)):
            raise reject("content", "파일 내용이 형식과 맞지 않아요.")
    except StorageError as e:
        STORAGE_ERRORS.labels(operation="verify").inc()
        log.exception("upload verify failed: %s", key)
        raise HTTPException(status_code=503) from e
    return kind


# ---------- 사진 연결·정렬·수정·삭제 ----------


def _owner_or_404(db: Session, target: str, owner_id: int) -> Base:
    item = db.get(OWNERS[target].model, owner_id)
    if item is None:
        raise HTTPException(status_code=404)
    return item


@router.post("/{target}/{owner_id}/images", status_code=201)
def attach_image(
    body: AttachIn,
    target: Target = Path(),
    owner_id: int = Path(),
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage),
    admin: AdminUser = Depends(current_admin),
) -> ImageOut:
    _owner_or_404(db, target, owner_id)
    column = OWNERS[target].column
    count = db.scalar(select(func.count()).select_from(Image).where(column == owner_id)) or 0
    if count >= MAX_IMAGES_PER_ITEM:
        raise HTTPException(status_code=422, detail=f"사진은 {MAX_IMAGES_PER_ITEM}장까지 올릴 수 있어요.")

    kind = verify_upload(storage, body.s3_key, "image")
    dest = new_key(f"images/{target}/{owner_id}", kind.ext)
    content_type = next(ct for ct, k in KINDS["image"].items() if k is kind)
    try:
        storage.copy(storage.media_bucket, body.s3_key, storage.media_bucket, dest, content_type, IMAGE_CACHE)
    except StorageError as e:
        STORAGE_ERRORS.labels(operation="copy").inc()
        log.exception("image copy failed: %s", body.s3_key)
        raise HTTPException(status_code=503) from e

    last = db.scalar(select(func.max(Image.sort_order)).where(column == owner_id))
    image = Image(s3_key=dest, alt_text=body.alt_text, sort_order=(last + 1) if last is not None else 0)
    setattr(image, column.key, owner_id)
    db.add(image)
    try:
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        log.exception("image save failed: %s/%d", target, owner_id)
        delete_files(storage, [dest])  # DB에 못 넣었으면 복사본도 지운다
        raise HTTPException(status_code=503) from e
    delete_files(storage, [body.s3_key])  # tmp 원본 (실패해도 1일 뒤 자동 삭제)
    log.info("image attached: admin=%s %s/%d image=%d", admin.username, target, owner_id, image.id)
    request_rebuild(f"image added to {target}/{owner_id}")
    return image_out(image)


@router.put("/{target}/{owner_id}/images/order")
def reorder_images(
    body: OrderIn,
    target: Target = Path(),
    owner_id: int = Path(),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(current_admin),
) -> list[ImageOut]:
    """첫 번째가 대표 사진. 그 항목의 사진 id를 빠짐없이, 한 번씩 보내야 한다."""
    _owner_or_404(db, target, owner_id)
    images = {i.id: i for i in images_of(db, target, owner_id)}
    if sorted(body.image_ids) != sorted(images):
        raise HTTPException(status_code=422, detail="이 항목의 사진 id를 빠짐없이 한 번씩 보내주세요.")
    for order, image_id in enumerate(body.image_ids):
        images[image_id].sort_order = order
    db.commit()
    request_rebuild(f"images reordered in {target}/{owner_id}")
    return [image_out(i) for i in images_of(db, target, owner_id)]


@router.patch("/images/{image_id}")
def update_image(
    image_id: int, body: AltIn, db: Session = Depends(get_db), _: AdminUser = Depends(current_admin)
) -> ImageOut:
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404)
    image.alt_text = body.alt_text
    db.commit()
    request_rebuild(f"image {image_id} alt text")
    return image_out(image)


@router.delete("/images/{image_id}", status_code=204)
def delete_image(
    image_id: int,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage),
    admin: AdminUser = Depends(current_admin),
) -> None:
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404)
    target, owner_id = owner_of(image)
    key = image.s3_key
    db.delete(image)
    db.commit()
    delete_files(storage, [key])
    log.info("image deleted: admin=%s %s/%d image=%d", admin.username, target, owner_id, image_id)
    request_rebuild(f"image deleted from {target}/{owner_id}")


# ---------- 소개서 ----------


class BrochureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    s3_key: str = Field(max_length=100)


@router.put("/settings/brochure")
def replace_brochure(
    body: BrochureIn,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage),
    admin: AdminUser = Depends(current_admin),
) -> dict[str, str]:
    """media 버킷 tmp → site 버킷 files/brochure.pdf (주소가 고정이라 CloudFront 캐시를 지운다)."""
    verify_upload(storage, body.s3_key, "brochure")
    try:
        storage.copy(storage.media_bucket, body.s3_key, storage.site_bucket, BROCHURE_KEY, "application/pdf", BROCHURE_CACHE)
    except StorageError as e:
        STORAGE_ERRORS.labels(operation="copy").inc()
        log.exception("brochure copy failed")
        raise HTTPException(status_code=503) from e
    db.merge(Setting(key="outreach.brochure_s3_key", value=BROCHURE_KEY, description="소개서 PDF 위치"))
    db.commit()
    delete_files(storage, [body.s3_key])
    try:
        storage.invalidate([f"/{BROCHURE_KEY}"])
    except StorageError:
        # 파일은 바뀌었다. 캐시(5분)가 끝나면 새 파일이 보인다
        STORAGE_ERRORS.labels(operation="invalidate").inc()
        log.exception("brochure invalidation failed")
    log.info("brochure replaced: admin=%s", admin.username)
    return {"brochure_url": public_url(BROCHURE_KEY)}
