from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수에서 읽는 설정. 서버에서는 deploy/compose.yaml이 넘겨준다."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # compose는 postgresql://... 형식으로 넘긴다. SQLAlchemy 드라이버(psycopg 3)를 붙여서 쓴다.
    database_url: str = "postgresql://dowha:dowha@localhost:5432/dowha"

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
