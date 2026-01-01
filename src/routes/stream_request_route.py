import asyncio
import json

from classes.StreamRequest import StreamRequest

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("/stream/get-request")
async def stream_get_request():
    """
    A simple GET request. Streamed step-by-step.
    """
    stream_requester = StreamRequest()

    return StreamingResponse(
        stream_requester.process_sse(), media_type="text/event-stream"
    )
