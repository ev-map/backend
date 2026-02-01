import base64
import binascii
import re
from typing import Any

import requests
from django.db.models import Q
from ninja import Schema
from ninja.security import HttpBearer
from requests import Response

from evmap_backend.data_sources.ocpi.models import OcpiConnection

link_regex = re.compile('<([^>]+)>; rel="next"')


def auth_header(token: str, encode: bool = True) -> str:
    if encode:
        return f"Token {base64.b64encode(token.encode('utf-8')).decode('utf-8')}"
    else:
        return f"Token {token}"


def _ocpi_request(
    url: str, token: str, method: str, body: str = None
) -> tuple[Any, Response]:
    headers = {}
    if body is not None:
        headers["Content-Type"] = "application/json"

    response = requests.request(
        method,
        url,
        data=body,
        headers={**headers, "Authorization": auth_header(token, encode=True)},
    )
    if response.status_code == 401:
        # retry with unencoded token
        response = requests.request(
            method,
            url,
            data=body,
            headers={**headers, "Authorization": auth_header(token, encode=False)},
        )
    response.raise_for_status()
    json = response.json()

    if json["status_code"] != 1000:
        raise Exception(f"OCPI error {json['status_code']}: {json['status_message']}")
    return response, json


def ocpi_get(url: str, token: str):
    response, json = _ocpi_request(url, token, "GET")
    return json["data"]


def ocpi_get_paginated(url: str, token: str):
    response, json = _ocpi_request(url, token, "GET")

    if not isinstance(json["data"], list):
        raise Exception("OCPI paginated response data is not a list")

    for item in json["data"]:
        yield item

    if "Link" in response.headers:
        # paginated response
        link = link_regex.match(response.headers["Link"]).group(1)
        for item in ocpi_get_paginated(link, token):
            yield item


def ocpi_post(url: str, token: str, body: Schema):
    dump_json = body.model_dump_json()
    response, json = _ocpi_request(url, token, "POST", dump_json)
    return json["data"]


class OcpiTokenAuth(HttpBearer):
    openapi_scheme = "token"

    def __init__(self, allow_token_a=False):
        self.allow_token_a = allow_token_a
        super().__init__()

    def authenticate(self, request, token):
        from evmap_backend.data_sources.registry import get_data_source

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
