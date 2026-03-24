import time
from typing import Awaitable, Callable

try:
    from models.expert_stream_models import ExpertStreamEvent
except ImportError:
    from src.models.expert_stream_models import ExpertStreamEvent


ProgressCallback = Callable[[ExpertStreamEvent], Awaitable[None]]


def format_expert_stream_event(event: ExpertStreamEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"


async def emit_expert_stream_event(
    *,
    progress_callback: ProgressCallback | None,
    event: str,
    stage: str,
    step: str,
    message: str,
    result: object | None = None,
    fallback_prefix: str | None = None,
) -> ExpertStreamEvent:
    stream_event = ExpertStreamEvent(
        event=event,
        timestamp=time.time(),
        stage=stage,
        step=step,
        message=message,
        result=result,
    )

    if progress_callback is not None:
        await progress_callback(stream_event)
    else:
        prefix = fallback_prefix or stage
        print(f"{prefix}: {message}")

    return stream_event
