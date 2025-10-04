import datetime as dt
import os
from collections import defaultdict

import requests
from django.core.management import BaseCommand
from tqdm import tqdm

from evmap_backend.data_sources.monta.models import MontaTokens

API_URL = "https://partner-api.monta.com/api/v1/afir/charge-points"
TOKEN_URL = "https://partner-api.monta.com/api/v1/auth/token"
REFRESH_URL = "https://partner-api.monta.com/api/v1/auth/refresh"
SOURCE = "monta"


class Command(BaseCommand):
    help = "Connects to Monta AFIR API to extract static charger information"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        tokens = MontaTokens.get_solo()
        now = dt.datetime.now().astimezone()
        if tokens.refresh_token_expires <= now:
            response = get_monta_token()
            tokens.access_token = response["accessToken"]
            tokens.refresh_token = response["refreshToken"]
            tokens.access_token_expires = dt.datetime.fromisoformat(
                response["accessTokenExpirationDate"]
            )
            tokens.refresh_token_expires = dt.datetime.fromisoformat(
                response["refreshTokenExpirationDate"]
            )
            tokens.save()
        elif tokens.access_token_expires <= now:
            response = refresh_monta_token(tokens.refresh_token)
            tokens.access_token = response["accessToken"]
            tokens.refresh_token = response["refreshToken"]
            tokens.access_token_expires = dt.datetime.fromisoformat(
                response["accessTokenExpirationDate"]
            )
            tokens.refresh_token_expires = dt.datetime.fromisoformat(
                response["refreshTokenExpirationDate"]
            )
            tokens.save()

        chargers_by_location = defaultdict(list)

        for charger in tqdm(get_all_monta_chargers(access_token=tokens.access_token)):
            chargers_by_location[charger["location"]["addressLabel"]].append(charger)

        print(chargers_by_location)
        print(len(chargers_by_location))


def get_monta_token():
    response = requests.post(
        TOKEN_URL,
        json={
            "clientId": os.environ.get("MONTA_CLIENT_ID"),
            "clientSecret": os.environ.get("MONTA_CLIENT_SECRET"),
        },
    )
    return response.json()


def refresh_monta_token(refresh_token):
    response = requests.post(REFRESH_URL, json={"refreshToken": refresh_token})
    return response.json()


def get_monta_data(access_token, after=None):
    response = requests.get(
        API_URL,
        params={"after": after} if after is not None else {},
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )
    response.raise_for_status()
    return response.json()


def get_all_monta_chargers(access_token):
    root = get_monta_data(access_token)
    for charger in root["data"]:
        yield charger

    while root["meta"]["after"] is not None:
        print(root["meta"]["after"])
        root = get_monta_data(access_token, after=root["meta"]["after"])
        for charger in root["data"]:
            yield charger
