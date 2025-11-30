import os

from evmap_backend.settings import *

DATABASES["default"] = {
    "ENGINE": "django.contrib.gis.db.backends.postgis",
    "NAME": os.environ.get("TEST_DB_NAME", "evmap_test"),
    "USER": os.environ.get("TEST_DB_USER", "postgres"),
    "PASSWORD": os.environ.get("TEST_DB_PASSWORD", "postgres"),
    "HOST": os.environ.get("TEST_DB_HOST", "127.0.0.1"),
    "PORT": os.environ.get("TEST_DB_PORT", "5432"),
}
