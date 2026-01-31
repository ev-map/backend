from django.db import models
from django.utils.crypto import get_random_string


def generate_token():
    return get_random_string(64)


class OcpiConnection(models.Model):
    data_source = models.CharField(max_length=255, unique=True)
    token_a = models.CharField(max_length=255, blank=True, default=generate_token)
    token_b = models.CharField(max_length=255, blank=True)
    token_c = models.CharField(max_length=255, blank=True)
    url = models.CharField(max_length=255, blank=True)
    version = models.CharField(max_length=10, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    party_id = models.CharField(max_length=10, blank=True)
    locations_url = models.CharField(max_length=255, blank=True)
    tariffs_url = models.CharField(max_length=255, blank=True)
