from typing import Any

from pydantic import BaseModel


class ExpertStreamEvent(BaseModel):
    event: str
    timestamp: float
    stage: str | None = None
    step: str | None = None
    message: str | None = None
    result: Any | None = None
