import datetime as dt

from django.db import models
from solo.models import SingletonModel


class MontaTokens(SingletonModel):
    access_token = models.CharField(max_length=255, blank=True)
    refresh_token = models.CharField(max_length=255, blank=True)
    access_token_expires = models.DateTimeField(
        default=dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    )
    refresh_token_expires = models.DateTimeField(
        default=dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    )
