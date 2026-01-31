import base64
import binascii
import re

import requests
from ninja.security import HttpBearer

from evmap_backend.data_sources.ocpi.models import OcpiConnection

link_regex = re.compile('<([^>]+)>; rel="next"')


def auth_header(token: str, encode: bool = True) -> str:
    if encode:
        return f"Token {base64.b64encode(token.encode('utf-8')).decode('utf-8')}"
    else:
        return f"Token {token}"


def ocpi_get(url, token: str):
    response = requests.get(
        url, headers={"Authorization": auth_header(token, encode=True)}
    )
    print(response.status_code)
    if response.status_code == 401:
        # retry with unencoded token
        response = requests.get(
            url, headers={"Authorization": auth_header(token, encode=False)}
        )
        print(response.status_code)
    response.raise_for_status()
    json = response.json()

    if json["status_code"] != 1000:
        raise Exception(f"OCPI error {json['status_code']}: {json['status_message']}")

    if isinstance(json["data"], list):
        for item in json["data"]:
            yield item

        if "Link" in response.headers:
            # paginated response
            link = link_regex.match(response.headers["Link"]).group(1)
            for item in ocpi_get(link, token):
                yield item
    else:
        return json["data"]


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
                return OcpiConnection.objects.get(token_c=t)
            except OcpiConnection.DoesNotExist:
                pass
            if self.allow_token_a:
                try:
                    return OcpiConnection.objects.get(token_a=t)
                except OcpiConnection.DoesNotExist:
                    pass
        return None
