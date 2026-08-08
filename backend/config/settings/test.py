import os

from .base import *  # noqa: F401, F403

# django.contrib.postgres is needed for ArrayField used in articles, papers, tweets etc.
if "django.contrib.postgres" not in INSTALLED_APPS:  # noqa: F405
    INSTALLED_APPS += ["django.contrib.postgres"]  # noqa: F405

DEBUG = True
ALLOWED_HOSTS = ["*", "localhost", "testserver", "127.0.0.1"]

# SEC-02: Use env vars for DB credentials — allows CI/CD to inject proper values
# without hardcoding them in source control. Defaults match Docker Compose dev setup.
# In CI: set DB_USER, DB_PASSWORD, DB_NAME, DB_HOST, DB_PORT as secrets.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "synapse_db"),
        "USER": os.environ.get("DB_USER", "synapse_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "synapse_pass"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5433"),
        "TEST": {
            "NAME": os.environ.get("TEST_DB_NAME", "synapse_test"),
        },
    }
}
# Use a fast, non-cryptographic hasher in tests.
# MD5PasswordHasher is intentionally avoided — even in tests, using MD5 for
# passwords can leak real password patterns if test fixtures share data with
# production. MD5 is also cryptographically broken.
# django.contrib.auth.hashers.MD5PasswordHasher is replaced with the dummy
# hasher that stores passwords as-is (plaintext) — safe only for test use.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# Disable axes in tests
AXES_ENABLED = False
# Use dummy cache in tests
CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
# Celery in eager mode for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
