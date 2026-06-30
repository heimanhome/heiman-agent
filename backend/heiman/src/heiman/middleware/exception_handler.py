import logging

from fastapi import Request, status
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from heiman.middleware.exceptions import BaseAPIException

logger = logging.getLogger(__name__)

SYSTEM_ERROR_CODE = 9000


def _create_error_response(
    status_code: int, code: int, message: str, data=None
) -> JSONResponse:
    response_data = {"code": code, "message": message, "data": data}
    return JSONResponse(status_code=status_code, content=response_data)


def _handle_base_api_exception(exc: BaseAPIException) -> JSONResponse:
    logger.error(
        "Request failed - %s: %s", type(exc).__name__, exc.message, exc_info=True
    )

    return _create_error_response(
        status_code=exc.http_status, code=exc.code, message=exc.message
    )


def handle_exception(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, RequestValidationError):
        logger.warning("Request validation failed: %s", exc)
        return _create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=1002,
            message="Request parameter validation failed",
            data=exc.errors(),
        )

    if isinstance(exc, BaseAPIException):
        return _handle_base_api_exception(exc)

    if isinstance(exc, FastAPIHTTPException):
        logger.warning("FastAPI HTTP error - %s: %s", exc.status_code, exc.detail)
        return _create_error_response(
            status_code=exc.status_code,
            code=1000,
            message=str(exc.detail),
        )

    exc_type = type(exc)
    logger.error(
        "Unhandled system error - %s: %s", exc_type.__name__, str(exc), exc_info=True
    )
    return _create_error_response(
        status_code=500,
        code=SYSTEM_ERROR_CODE,
        message="Internal server error " + exc_type.__name__ + ": " + str(exc),
    )