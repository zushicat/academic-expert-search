# from classes.SimpleRequest import SimpleRequest
# from models.simple_request_models import SimpleRequestIn, SimpleRequestResponse

import asyncio
from contextlib import suppress

from classes.ExpertSearch import ExpertSearch
from classes.ExpertRecommender import ExpertRecommender

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from helpers.expert_stream import (
    emit_expert_stream_event,
    format_expert_stream_event,
    ProgressCallback,
)
from helpers.short_search_response import create_short_search_response
from helpers.toon import encode_toon
from helpers.short_recommender_response import create_short_recommender_response
from models.expert_stream_models import ExpertStreamEvent

router = APIRouter()


def _create_streaming_response(
    request: Request,
    worker_factory,
) -> StreamingResponse:
    async def event_generator():
        queue: asyncio.Queue[ExpertStreamEvent | None] = asyncio.Queue()

        async def progress_callback(event: ExpertStreamEvent):
            await queue.put(event)

        async def worker():
            try:
                await worker_factory(progress_callback)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await emit_expert_stream_event(
                    progress_callback=progress_callback,
                    event="error",
                    stage="stream",
                    step="failed",
                    message=str(exc),
                )
            finally:
                await queue.put(None)

        worker_task = asyncio.create_task(worker())

        try:
            while True:
                if await request.is_disconnected():
                    worker_task.cancel()
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    continue

                if event is None:
                    break

                yield format_expert_stream_event(event)
        finally:
            if not worker_task.done():
                worker_task.cancel()

            with suppress(asyncio.CancelledError):
                await worker_task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/expert/search")
async def expert_search(
    query: str = Query(default="", description="A string"),
    use_fulltext_search: bool = Query(
        default=False, description="set openalex query: title/abstract or fullsearch"
    ),
    create_queries: bool = Query(
        default=False, description="create a list of queries by LLM first"
    ),
    short_response: bool = Query(
        default=True,
        description="Get the shortened version of the response",
    ),
):
    """
    A GET requests with the parameters
    - query

    Response:
    A JSON object with objects
    - Status: "ok" or "error"
    - Response: A response from the called class

    Intentionally not using Pydantic model, here.
    """
    try:
        searcher = ExpertSearch()
        search_response = await searcher.search_experts(
            query=query,
            use_fulltext_search=use_fulltext_search,
            create_queries=create_queries,
        )

        if short_response:
            search_response = create_short_search_response(
                response=search_response.model_dump()
            )

        return {"Status": "ok", "Response": search_response}
    except Exception as e:
        return {"Status": "Error", "Response": str(e)}


@router.get("/expert/search/stream")
async def expert_search_stream(
    request: Request,
    query: str = Query(default="", description="A string"),
    use_fulltext_search: bool = Query(
        default=False, description="set openalex query: title/abstract or fullsearch"
    ),
    create_queries: bool = Query(
        default=False, description="create a list of queries by LLM first"
    ),
    short_response: bool = Query(
        default=True,
        description="Get the shortened version of the response",
    ),
):
    async def worker(progress_callback: ProgressCallback):
        await emit_expert_stream_event(
            progress_callback=progress_callback,
            event="started",
            stage="search",
            step="start",
            message="Starting expert search",
        )

        searcher = ExpertSearch()
        search_response = await searcher.search_experts(
            query=query,
            use_fulltext_search=use_fulltext_search,
            create_queries=create_queries,
            progress_callback=progress_callback,
        )

        result = search_response.model_dump()
        if short_response:
            result = create_short_search_response(response=result)

        await emit_expert_stream_event(
            progress_callback=progress_callback,
            event="completed",
            stage="search",
            step="completed",
            message="Search stream completed",
            result=result,
        )

    return _create_streaming_response(request, worker)


@router.get("/expert/recommender", response_model=None)
async def expert_recommender(
    query: str = Query(default="", description="The search query string"),
    create_expert_summaries: bool = Query(
        default=False,
        description="Wether to create a summary for ewach author based on works or not.",
    ),
    top_perc_found_authors: float = Query(
        default=0.8, description="Threshold for author results from search"
    ),
    use_fulltext_search: bool = Query(
        default=False, description="set openalex query: title/abstract or fullsearch"
    ),
    create_queries: bool = Query(
        default=False, description="create a list of queries by LLM first"
    ),
    short_response: bool = Query(
        default=True,
        description="Get the shortened version of the response",
    ),
    toon: bool = Query(
        default=False,
        description="Return the recommender response in Toon format (or JSON)",
    ),
):
    """
    A GET requests with the parameters
    - query

    Response:
    A JSON object with objects
    - Status: "ok" or "error"
    - Response: A response from the called class

    Intentionally not using Pydantic model, here.
    """
    if not query:
        return {"Status": "Error", "Response": "You must pass a search query."}
    try:
        searcher = ExpertSearch()
        search_response = await searcher.search_experts(
            query=query,
            use_fulltext_search=use_fulltext_search,
            create_queries=create_queries,
        )

        recommender = ExpertRecommender(top_perc_found_authors=top_perc_found_authors)
        recommender_response = await recommender.recommend_experts(
            search_result=search_response,
            create_expert_summaries=create_expert_summaries,
        )

        if short_response:
            recommender_response = create_short_recommender_response(
                response=recommender_response
            )

        if toon:
            recommender_response = encode_toon(json_data=recommender_response)

        return {"Status": "ok", "Response": recommender_response}
    except Exception as e:
        return {"Status": "Error", "Response": str(e)}


@router.get("/expert/recommender/stream", response_model=None)
async def expert_recommender_stream(
    request: Request,
    query: str = Query(default="", description="The search query string"),
    create_expert_summaries: bool = Query(
        default=False,
        description="Wether to create a summary for ewach author based on works or not.",
    ),
    top_perc_found_authors: float = Query(
        default=0.8, description="Threshold for author results from search"
    ),
    use_fulltext_search: bool = Query(
        default=False, description="set openalex query: title/abstract or fullsearch"
    ),
    create_queries: bool = Query(
        default=False, description="create a list of queries by LLM first"
    ),
    short_response: bool = Query(
        default=True,
        description="Get the shortened version of the response",
    ),
    toon: bool = Query(
        default=False,
        description="Return the recommender response in Toon format (or JSON)",
    ),
):
    async def worker(progress_callback: ProgressCallback):
        if not query:
            await emit_expert_stream_event(
                progress_callback=progress_callback,
                event="error",
                stage="recommender",
                step="validate_query",
                message="You must pass a search query.",
            )
            return

        await emit_expert_stream_event(
            progress_callback=progress_callback,
            event="started",
            stage="recommender",
            step="start",
            message="Starting expert recommender",
        )

        searcher = ExpertSearch()
        search_response = await searcher.search_experts(
            query=query,
            use_fulltext_search=use_fulltext_search,
            create_queries=create_queries,
            progress_callback=progress_callback,
        )

        recommender = ExpertRecommender(top_perc_found_authors=top_perc_found_authors)
        recommender_response = await recommender.recommend_experts(
            search_result=search_response,
            create_expert_summaries=create_expert_summaries,
            progress_callback=progress_callback,
        )

        if short_response:
            recommender_response = create_short_recommender_response(
                response=recommender_response
            )

        if toon:
            recommender_response = encode_toon(json_data=recommender_response)

        await emit_expert_stream_event(
            progress_callback=progress_callback,
            event="completed",
            stage="recommender",
            step="completed",
            message="Recommender stream completed",
            result=recommender_response,
        )

    return _create_streaming_response(request, worker)
