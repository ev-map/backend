import base64
import re
from typing import Any

import requests
from ninja import Schema
from requests import Response

link_regex = re.compile('<([^>]+)>; rel="next"')


def auth_header(token: str, encode: bool = True) -> str:
    if encode:
        return f"Token {base64.b64encode(token.encode('utf-8')).decode('utf-8')}"
    else:
        return f"Token {token}"


def _ocpi_request(
    url: str, token: str, method: str, body: str = None, extra_auth_header: str = None
) -> tuple[Any, Response]:
    headers = {"Authorization": auth_header(token, encode=True)}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if extra_auth_header is not None:
        # add extra auth header (Instavolt requires x-api-key)
        headers[extra_auth_header] = auth_header(token, encode=True)

    response = requests.request(
        method,
        url,
        data=body,
        headers=headers,
    )
    if response.status_code == 401:
        # retry with unencoded token
        headers["Authorization"] = auth_header(token, encode=False)
        if extra_auth_header is not None:
            headers[extra_auth_header] = auth_header(token, encode=False)
        response = requests.request(
            method,
            url,
            data=body,
            headers=headers,
        )
    response.raise_for_status()
    json = response.json()

    if json["status_code"] != 1000:
        raise Exception(f"OCPI error {json['status_code']}: {json['status_message']}")
    return response, json


def ocpi_get(url: str, token: str, extra_auth_header: str = None):
    response, json = _ocpi_request(
        url, token, "GET", extra_auth_header=extra_auth_header
    )
    return json["data"]


def ocpi_get_paginated(url: str, token: str, extra_auth_header: str = None):
    response, json = _ocpi_request(
        url, token, "GET", extra_auth_header=extra_auth_header
    )

    if not isinstance(json["data"], list):
        raise Exception("OCPI paginated response data is not a list")

    for item in json["data"]:
        yield item

    if "Link" in response.headers:
        # paginated response
        link = link_regex.match(response.headers["Link"]).group(1)
        for item in ocpi_get_paginated(
            link, token, extra_auth_header=extra_auth_header
        ):
            yield item


def ocpi_post(url: str, token: str, body: Schema):
    dump_json = body.model_dump_json()
    response, json = _ocpi_request(url, token, "POST", dump_json)
    return json["data"]
