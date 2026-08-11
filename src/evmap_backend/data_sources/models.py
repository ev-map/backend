from django.db import models


class UpdateState(models.Model):
    data_source = models.CharField(
        max_length=255, primary_key=True, blank=False, null=False
    )
    last_update = models.DateTimeField(auto_now=True)
    push = models.BooleanField(blank=False, null=False)


class OAuthToken(models.Model):
    id = models.CharField(primary_key=True, max_length=255, blank=False)
    access_token = models.CharField(max_length=255, blank=False)
    refresh_token = models.CharField(max_length=255, blank=False)
    access_token_expires = models.DateTimeField(null=True)
    refresh_token_expires = models.DateTimeField(null=True)
