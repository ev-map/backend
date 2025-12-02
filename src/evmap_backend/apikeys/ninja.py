from ninja.security import APIKeyHeader

from evmap_backend.apikeys.models import ApiKey


class ApiKeyAuth(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        try:
            return ApiKey.objects.get(key=key)
        except ApiKey.DoesNotExist:
            pass
