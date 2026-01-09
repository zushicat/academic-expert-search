from routes import root_route, simple_request_route, stream_request_route

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from auth import bearer_auth_dependency

app = FastAPI(dependencies=[Depends(bearer_auth_dependency)])

# Import and include routers
app.include_router(root_route.router)
app.include_router(simple_request_route.router)
app.include_router(stream_request_route.router)


# add exception handling
@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=404,
        content={"Status": "Error", "Response": "Endpoint not existing"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_msg = str(exc.errors()[0]["msg"])
    return JSONResponse(
        status_code=400,
        content={"Status": "Error", "Response": f"Value error, {error_msg}"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=400, content={"Status": "Error", "Response": str(exc)}
    )
