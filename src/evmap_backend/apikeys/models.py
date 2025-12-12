from django.db import models
from django.utils.crypto import get_random_string


def _generate_api_key():
    return get_random_string(64)


class ApiKey(models.Model):
    key = models.CharField(
        max_length=255, unique=True, primary_key=True, default=_generate_api_key
    )
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    @property
    def truncated_key(self):
        return f"{self.key[:10]}..."

    def __str__(self):
        return f"APIKey(owner={self.description}, active={self.active})"
