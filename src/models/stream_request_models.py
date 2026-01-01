from typing import Any, Dict, List
from pydantic import BaseModel, ConfigDict


class StreamEvent(BaseModel):
    event: str
    timestamp: float

    model_config = ConfigDict(extra="allow")


class Book(BaseModel):
    id: str
    title: str | None = None


class Topic(BaseModel):
    id: str
    topics: List[str]


class MergedBook(BaseModel):
    id: str
    title: str | None = None
    topics: List[str]
