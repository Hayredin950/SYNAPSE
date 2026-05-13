import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# ── Langchain compatibility patch ─────────────────────────────────────────────
# langchain-openai >= 0.2.14 imports ContextOverflowError from langchain-core,
# but langchain-core 0.3.83 does not include it. Patch it in before any import.
try:
    from langchain_core import exceptions as _lc_exc

    if not hasattr(_lc_exc, "ContextOverflowError"):

        class ContextOverflowError(_lc_exc.LangChainException):
            """Context window exceeded — compatibility shim."""

        _lc_exc.ContextOverflowError = ContextOverflowError
except Exception:
    pass
# ─────────────────────────────────────────────────────────────────────────────

application = get_wsgi_application()
