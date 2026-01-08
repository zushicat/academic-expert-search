from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_KEY: str | None = None
    USE_API_KEY: bool | None = False

    LLM_ANALYZER_MODEL: str | None = None
    LLM_ANALYZER_BASE_URL: str | None = None
    LLM_ANALYZER_API_KEY: str | None = None


config = Settings()
