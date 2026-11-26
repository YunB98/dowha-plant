from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수에서 읽는 설정. 서버에서는 deploy/compose.yaml이 넘겨준다."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # dev / staging / prod. prod에서는 /api/docs를 닫는다 (api-spec 3장)
    app_env: str = "dev"

    # compose는 postgresql://... 형식으로 넘긴다. SQLAlchemy 드라이버(psycopg 3)를 붙여서 쓴다.
    database_url: str = "postgresql://dowha:dowha@localhost:5432/dowha"

    # 문의 알림. 비어 있으면 보내지 않는다 (로컬, 테스트)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

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
