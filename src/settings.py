from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_KEY: str | None = None
    USE_API_KEY: bool | None = False

    OPENALEX_API_KEY: str | None

    LLM_ANALYZER_MAX_CONCURRENCY: int = 5
    LLM_ANALYZER_BATCH_SIZE: int = 4
    LLM_ANALYZER_TIMEOUT: int = 30
    LLM_ANALYZER_REASONING_EFFORT: str | None = None

    LLM_QUERY_EXPANSION_MAX_CONCURRENCY: int = 5
    LLM_QUERY_EXPANSION_BATCH_SIZE: int = 4
    LLM_QUERY_EXPANSION_TIMEOUT: int = 30
    LLM_QUERY_EXPANSION_REASONING_EFFORT: str | None = None

    # LLM_JSON_REPAIR_REASONING_EFFORT: str | None = None

    LLM_ANALYZER_MODEL: str | None = None
    LLM_ANALYZER_BASE_URL: str | None = None
    LLM_ANALYZER_API_KEY: str | None = None

    # LLM_JSON_REPAIR_MODEL: str | None = None
    # LLM_JSON_REPAIR_BASE_URL: str | None = None
    # LLM_JSON_REPAIR_API_KEY: str | None = None

    LLM_QUERY_EXPANSION_MODEL: str | None = None
    LLM_QUERY_EXPANSION_BASE_URL: str | None = None
    LLM_QUERY_EXPANSION_API_KEY: str | None = None


config = Settings()
