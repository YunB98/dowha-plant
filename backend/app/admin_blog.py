"""사장님 블로그 글 관리 (기능명세 A-05, ADR 0027). 모든 요청은 로그인 필요.

자동으로 들어온 글에 판매 정보를 붙이고, 자동 분류가 틀렸으면 고친다. 아무것도 하지 않아도 글은 진열된다.
- PATCH는 보낸 항목만 바꾼다. display_name을 null로 보내면 블로그 제목으로 돌아간다
- 목적 태그는 사이트 필터 6개 중에서만
- 가격·판매 상태·크기는 null(또는 빈 문자열)로 지울 수 있다
- 공개 내용이 바뀌므로 사이트 재빌드를 요청한다 (ADR 0015)
"""

import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_admin
from app.blog_import import PURPOSES, default_name
from app.db import get_db
from app.models import AdminUser, BlogPost, PlantGuide
from app.public import public_url
from app.site_rebuild import request_rebuild

router = APIRouter(prefix="/api/v1/admin/blog-posts", tags=["admin-blog"], dependencies=[Depends(current_admin)])
log = logging.getLogger("dowha.admin")

Kind = Literal["plant", "class", "outreach", "gift", "other"]
SaleStatus = Literal["available", "reserved", "sold"]
assert set(Kind.__args__) == set(BlogPost.KINDS)
assert set(SaleStatus.__args__) == set(BlogPost.SALE_STATUSES)


class BlogPostOut(BaseModel):
    id: int
    title: str
    display_name: str | None
    name: str  # 화면에 보이는 이름
    excerpt: str
    kind: str
    tags: list[str]
    purposes: list[str]
    sale_status: str | None
    price: int | None
    size: str
    plant_guide_id: int | None
    is_hidden: bool
    thumbnail_url: str | None
    blog_url: str
    published_at: datetime


class BlogPostUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(None, max_length=100)
    kind: Kind | None = None
    purposes: list[str] | None = None
    sale_status: SaleStatus | None = None
    price: int | None = Field(None, ge=0, le=10_000_000)
    size: str | None = Field(None, max_length=50)
    plant_guide_id: int | None = None
    is_hidden: bool | None = None

    @field_validator("purposes")
    @classmethod
    def _purposes(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        unknown = [p for p in v if p not in PURPOSES]
        if unknown:
            raise ValueError(f"고를 수 있는 목적: {', '.join(PURPOSES)}")
        return [p for p in PURPOSES if p in v]  # 중복 제거, 필터 순서대로


def _out(p: BlogPost) -> BlogPostOut:
    return BlogPostOut(
        id=p.id, title=p.title, display_name=p.display_name, name=p.display_name or default_name(p.title),
        excerpt=p.excerpt, kind=p.kind, tags=p.tags, purposes=p.purposes, sale_status=p.sale_status,
        price=p.price, size=p.size, plant_guide_id=p.plant_guide_id, is_hidden=p.is_hidden,
        thumbnail_url=public_url(p.thumbnail_s3_key) if p.thumbnail_s3_key else None,
        blog_url=p.guid, published_at=p.published_at,
    )


@router.get("")
def list_posts(kind: Kind | None = None, db: Session = Depends(get_db)) -> list[BlogPostOut]:
    q = select(BlogPost).order_by(BlogPost.published_at.desc(), BlogPost.id.desc())
    if kind:
        q = q.where(BlogPost.kind == kind)
    return [_out(p) for p in db.scalars(q)]


@router.patch("/{post_id}")
def update_post(post_id: int, body: BlogPostUpdate, db: Session = Depends(get_db),
                admin: AdminUser = Depends(current_admin)) -> BlogPostOut:
    post = db.get(BlogPost, post_id)
    if post is None:
        raise HTTPException(status_code=404)
    data = {k: getattr(body, k) for k in body.model_fields_set}
    for k in ("kind", "purposes", "is_hidden"):  # 비울 수 없는 항목
        if k in data and data[k] is None:
            raise HTTPException(status_code=422, detail=f"비울 수 없는 항목이에요: {k}")
    if data.get("plant_guide_id") is not None and db.get(PlantGuide, data["plant_guide_id"]) is None:
        raise HTTPException(status_code=422, detail="연결할 식물 가이드가 없어요.")
    if "display_name" in data and not data["display_name"]:
        data["display_name"] = None  # 블로그 제목으로 돌아간다
    if "size" in data and data["size"] is None:
        data["size"] = ""
    for k, v in data.items():
        setattr(post, k, v)
    db.commit()
    db.refresh(post)
    log.info("blog post updated: admin=%s post=%d fields=%s", admin.username, post.id, ",".join(sorted(data)))
    request_rebuild(f"blog post {post.id} updated")
    return _out(post)
