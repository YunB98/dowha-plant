# backend — 도화 API (FastAPI)

| 항목 | 내용 |
|---|---|
| 프레임워크 | FastAPI, SQLAlchemy 2.0, Alembic, psycopg 3 |
| DB | PostgreSQL 17.5 (운영은 같은 서버의 컨테이너) |
| 문서 | 실행 후 `/api/docs`, 설계는 `docs/api-spec.md`, `docs/db-schema.md` |

## 로컬 개발
```bash
# DB
docker run -d --name dowha-pg-dev -e POSTGRES_USER=dowha -e POSTGRES_PASSWORD=dowha \
  -e POSTGRES_DB=dowha -p 127.0.0.1:55432:5432 postgres:17.5-alpine

# 환경
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql://dowha:dowha@127.0.0.1:55432/dowha
# Windows에서는 PYTHONUTF8=1 도 설정 (한글이 든 파일을 cp949로 읽지 않게)

alembic upgrade head
uvicorn app.main:app --reload
pytest
```

## 스키마 바꾸기 (ADR 0024)
1. `app/models.py` 수정
2. `alembic revision --autogenerate -m "설명"` → 생성된 파일을 **직접 검토** (이름 바꾸기가 삭제+추가로 나오지 않았는지)
3. `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head` 로 왕복 확인
4. `pytest` — `test_models_match_migrations`가 빠진 마이그레이션을 잡는다

배포하면 API 컨테이너가 시작할 때 `alembic upgrade head`를 실행한다 (`start.sh`).
컬럼 삭제·이름 변경은 두 번의 배포로 나눈다 (ADR 0024 "한계와 규칙").
