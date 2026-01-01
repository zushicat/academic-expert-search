from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_KEY: str | None = None
    USE_API_KEY: bool | None = False


config = Settings()
