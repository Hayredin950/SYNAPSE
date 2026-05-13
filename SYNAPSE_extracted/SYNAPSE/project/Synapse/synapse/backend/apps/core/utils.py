from django.http import JsonResponse


def axes_lockout_response(request, credentials, *args, **kwargs):
    return JsonResponse(
        {
            "success": False,
            "error": {
                "code": 429,
                "message": "Too many failed login attempts. Please try again in 15 minutes.",
            },
        },
        status=429,
    )
