import base64
import binascii

from django.db.models import Q
from ninja.security import HttpBearer

from evmap_backend.data_sources.ocpi.models import OcpiConnection
from evmap_backend.data_sources.registry import get_data_source


class OcpiTokenAuth(HttpBearer):
    openapi_scheme = "token"

    def __init__(self, allow_token_a=False):
        self.allow_token_a = allow_token_a
        super().__init__()

    def authenticate(self, request, token):
        token_variants = [token]
        try:
            token_decoded = base64.b64decode(token).decode("utf-8")
            token_variants.insert(0, token_decoded)
        except binascii.Error:
            pass
        except UnicodeDecodeError:
            pass

        for t in token_variants:
            try:
                conn = OcpiConnection.objects.get(
                    Q(token_a=t) | Q(token_b=t) | Q(token_c=t)
                )
                data_source = get_data_source(conn.data_source)
                if data_source.is_credentials_sender and t == conn.token_b:
                    return conn
                if not data_source.is_credentials_sender:
                    if t == conn.token_a and self.allow_token_a:
                        return conn
                    elif t == conn.token_c:
                        return conn
            except OcpiConnection.DoesNotExist:
                pass
        return None
