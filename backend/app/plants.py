"""손님용 식물 목록 (블로그 식물 소개 글, ADR 0027, 기능명세 C-02~C-05).

- 식물로 분류되고(kind=plant) 숨기지 않은 글만, 최신순
- 이름은 사장님이 정한 짧은 이름, 없으면 말머리를 뗀 블로그 제목
- 관리 가이드는 공개된 것만 연결한다 (비공개 가이드로 가는 링크를 만들지 않는다)
- 전체 글은 블로그 주소(blog_url)로 연결한다
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.blog_import import default_name
from app.db import get_db
from app.models import BlogPost, PlantGuide
from app.public import public_url

router = APIRouter(prefix="/api/v1", tags=["public"])


class PlantOut(BaseModel):
    id: int
    name: str
    excerpt: str
    thumbnail_url: str | None
    purposes: list[str]
    sale_status: str | None
    price: int | None
    size: str
    published_at: datetime
    blog_url: str
    guide_slug: str | None


def display_name(p: BlogPost) -> str:
    return p.display_name or default_name(p.title)


def _query():  # noqa: ANN202
    published_guide = case((PlantGuide.status == "published", PlantGuide.slug), else_=None)
    return (
        select(BlogPost, published_guide)
        .outerjoin(PlantGuide, BlogPost.plant_guide_id == PlantGuide.id)
        .where(BlogPost.kind == "plant", BlogPost.is_hidden.is_(False))
    )


def _out(p: BlogPost, guide_slug: str | None) -> PlantOut:
    return PlantOut(
        id=p.id, name=display_name(p), excerpt=p.excerpt,
        thumbnail_url=public_url(p.thumbnail_s3_key) if p.thumbnail_s3_key else None,
        purposes=p.purposes, sale_status=p.sale_status, price=p.price, size=p.size,
        published_at=p.published_at, blog_url=p.guid, guide_slug=guide_slug,
    )


@router.get("/plants")
def plants(db: Session = Depends(get_db)) -> list[PlantOut]:
    rows = db.execute(_query().order_by(BlogPost.published_at.desc(), BlogPost.id.desc())).all()
    return [_out(p, slug) for p, slug in rows]


@router.get("/plants/{plant_id}")
def plant(plant_id: int, db: Session = Depends(get_db)) -> PlantOut:
    row = db.execute(_query().where(BlogPost.id == plant_id)).one_or_none()
    if row is None:
        raise HTTPException(status_code=404)
    return _out(*row)
