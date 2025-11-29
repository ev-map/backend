from evmap_backend.settings import *

DATABASES["default"] = {
    "ENGINE": "django.contrib.gis.db.backends.postgis",
    "NAME": "evmap_test",
    "USER": "postgres",
    "PASSWORD": "postgres",
    "HOST": "127.0.0.1",
}
