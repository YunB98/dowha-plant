# 서버가 ARM(t4g)이라 CI에서 linux/arm64로 빌드한다.
FROM python:3.13.5-slim

# MALLOC_MMAP_THRESHOLD_: 큰 할당(로그인 해시 19MiB)을 항상 mmap으로 받아 해제 즉시 OS에 돌려준다.
#   glibc 기본값은 큰 블록을 한 번 해제하면 기준을 올려서, 이후 19MiB가 스레드별 힙에 남는다.
#   동시 로그인 측정: 기본값 74→140~152MiB(한도 160MiB), 고정 후 20건에도 76MiB
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MALLOC_MMAP_THRESHOLD_=131072 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY alembic.ini start.sh ./
COPY migrations ./migrations

RUN useradd --system --uid 10001 app
USER app

EXPOSE 8000

# 이미지에 curl이 없으므로 파이썬으로 확인한다.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"]

# 마이그레이션 적용 후 uvicorn 실행
CMD ["sh", "./start.sh"]
