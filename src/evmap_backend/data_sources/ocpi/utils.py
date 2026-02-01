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
