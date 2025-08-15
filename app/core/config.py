from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl
from typing import List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # 알 수 없는 키 무시(선택)
    )
    
    
    APP_ENV: str = "local"
    APP_NAME: str = "VoicePhish Sim"
    API_PREFIX: str = "/api"

    CORS_ORIGINS: List[AnyHttpUrl] = []

    # DB (방법1 기준)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "voicephish"
    POSTGRES_USER: str = "vpuser"
    POSTGRES_PASSWORD: str = "0320"
    SYNC_ECHO: bool = False

    # Keys
    OPENAI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None  # 피해자를 Gemini로 전환할 때 필요

    # 역할별 모델명
    ATTACKER_MODEL: str = "gpt-4.1-mini"
    VICTIM_MODEL: str = "gpt-4.1-mini"
    ADMIN_MODEL: str = "gpt-4.1-mini"

    # 피해자 프로바이더 선택: "openai" | "gemini"
    VICTIM_PROVIDER: str = "openai"

    # 턴 제한
    MAX_OFFENDER_TURNS: int = 10
    MAX_VICTIM_TURNS: int = 10

    @property
    def sync_dsn(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

settings = Settings()  # type: ignore
