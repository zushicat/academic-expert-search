# from classes.SimpleRequest import SimpleRequest
# from models.simple_request_models import SimpleRequestIn, SimpleRequestResponse

from classes.ExpertSearch import ExpertSearch
from classes.ExpertRecommender import ExpertRecommender

from fastapi import APIRouter, Query

from helpers.toon import encode_toon
from helpers.short_recommender_response import create_short_recommender_response

router = APIRouter()


@router.get("/expert/search")
async def expert_search(
    query: str = Query(default="", description="A string"),
    use_fulltext_search: bool = Query(
        default=False, description="set openalex query: title/abstract or fullsearch"
    ),
    create_queries: bool = Query(
        default=False, description="create a list of queries by LLM first"
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

        return {"Status": "ok", "Response": search_response}
    except Exception as e:
        return {"Status": "Error", "Response": str(e)}


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
