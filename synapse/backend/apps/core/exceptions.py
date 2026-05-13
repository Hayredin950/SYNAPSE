import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {
            "success": False,
            "error": {
                "code": response.status_code,
                "message": _get_error_message(response.data),
                "details": response.data,
            },
        }
    else:
        logger.exception("Unhandled exception", exc_info=exc)
        response = Response(
            {
                "success": False,
                "error": {
                    "code": 500,
                    "message": "Internal server error.",
                    "details": {},
                },
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return response


def _get_error_message(data):
    if isinstance(data, dict):
        if "detail" in data:
            return str(data["detail"])
        return "Validation error."
    if isinstance(data, list):
        return str(data[0]) if data else "Error."
    return str(data)
