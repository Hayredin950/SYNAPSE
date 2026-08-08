"""
backend.apps.core.middleware
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
TASK-105-4: Add X-API-Version header to all API responses.

Appends `X-API-Version: 1` to every response that goes through /api/ routes.
Non-API routes (frontend assets, admin) are left untouched.
"""


class APIVersionHeaderMiddleware:
    """
    Injects ``X-API-Version: 1`` into every HTTP response for paths under /api/.

    Usage — add to MIDDLEWARE in settings/base.py AFTER SecurityMiddleware:
        'apps.core.middleware.APIVersionHeaderMiddleware',
    """

    API_VERSION = "1"
    API_PREFIX = "/api/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.path.startswith(self.API_PREFIX):
            response["X-API-Version"] = self.API_VERSION

        return response
