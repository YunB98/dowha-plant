from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수에서 읽는 설정. 서버에서는 deploy/compose.yaml이 넘겨준다."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # dev / staging / prod. prod에서는 /api/docs를 닫는다 (api-spec 3장)
    app_env: str = "dev"

    # compose는 postgresql://... 형식으로 넘긴다. SQLAlchemy 드라이버(psycopg 3)를 붙여서 쓴다.
    database_url: str = "postgresql://dowha:dowha@localhost:5432/dowha"

    # 사진·파일 주소를 만들 때 쓰는 사이트 주소 (CloudFront)
    public_base_url: str = "https://dowha-plant.shop"

    # 문의 알림. 비어 있으면 보내지 않는다 (로컬, 테스트)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # 사진(media 버킷 images/)과 소개서(site 버킷 files/). 비어 있으면 업로드 API가 503 (로컬, 테스트)
    aws_region: str = "ap-northeast-2"
    media_bucket: str = ""
    site_bucket: str = ""
    cloudfront_distribution_id: str = ""

    # 블로그 글 가져오기 (ADR 0027)
    blog_rss_url: str = "https://rss.blog.naver.com/dowha_plantshop.xml"

    # 관리자 로그인 토큰 서명 키. 운영에서는 SSM session-secret (deploy.sh → .env → compose).
    # 바꾸면 발급된 토큰이 모두 무효가 된다 (전체 로그아웃).
    session_secret: str = ""

    @property
    def signing_key(self) -> str:
        if len(self.session_secret) >= 32:
            return self.session_secret
        if self.is_prod:
            raise RuntimeError("SESSION_SECRET이 없거나 너무 짧습니다 (32자 이상)")
        return "dev-only-session-secret-do-not-use-in-prod"

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
