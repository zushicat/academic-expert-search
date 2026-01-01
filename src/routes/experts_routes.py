# from classes.SimpleRequest import SimpleRequest
# from models.simple_request_models import SimpleRequestIn, SimpleRequestResponse

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/expert/search")
async def expert_search(query: str = Query(default="", description="A string")):
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
        # simple_requester = SimpleRequest(number=number, text=text, boolean=boolean)
        response = "some response"  # simple_requester.get_processed_data()

        return {"Status": "ok", "Response": response}
    except Exception as e:
        return {"Status": "Error", "Response": str(e)}
