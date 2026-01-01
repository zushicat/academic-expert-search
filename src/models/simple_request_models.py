from typing import Literal

from pydantic import BaseModel, Field


class SimpleRequestIn(BaseModel):
    number: int = Field(default=0, ge=0, le=2)
    text: str = ""
    boolean: bool = False


class SimpleRequestData(BaseModel):
    number: int
    text: str | None
    boolean: bool


class SimpleRequestResponse(BaseModel):
    Status: Literal["ok", "Error"]
    Response: SimpleRequestData | str
