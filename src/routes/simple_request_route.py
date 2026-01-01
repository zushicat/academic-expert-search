from classes.SimpleRequest import SimpleRequest
from models.simple_request_models import SimpleRequestIn, SimpleRequestResponse

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/simple/get-request")
async def simple_get_request(
    number: int = Query(default=0, ge=0, le=2, description="A number between 0 and 2"),
    text: str = Query(default="", description="A string"),
    boolean: bool = Query(
        default=False,
        description="A bool value",
    ),
):
    """
    A GET requests with the parameters
    - number
    - text
    - bool

    Response:
    A JSON object with objects
    - Status: "ok" or "error"
    - Response: A response from the called class

    Intentionally not using Pydantic model, here.
    """
    try:
        simple_requester = SimpleRequest(number=number, text=text, boolean=boolean)
        response = simple_requester.get_processed_data()

        return {"Status": "ok", "Response": response}
    except Exception as e:
        return {"Status": "Error", "Response": str(e)}


@router.post("/simple/post-request", response_model=SimpleRequestResponse)
async def simple_post_request(payload: SimpleRequestIn):
    """
    A POST request expecting an object adhering the Pydantic model SimpleRequestIn

    Response:
    A JSON object with objects
    - Status: "ok" or "error"
    - Response: A response from the called class adhering  the Pydantic model SimpleRequestResponse
    """
    try:
        simple_requester = SimpleRequest(
            number=payload.number,
            text=payload.text,
            boolean=payload.boolean,
        )
        response = simple_requester.get_processed_data()

        return {"Status": "ok", "Response": response}
    except Exception as e:
        return {"Status": "Error", "Response": str(e)}
