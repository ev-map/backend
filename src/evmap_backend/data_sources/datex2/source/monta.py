import datetime
import os
from abc import abstractmethod

import requests
from django.utils import timezone
from django.utils.functional import classproperty

from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.datex2.parser.json import Datex2JsonParser
from evmap_backend.data_sources.models import OAuthToken
from evmap_backend.data_sources.sync import sync_chargers


class BaseMontaPublicDatex2DataSource(DataSource):
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    parser = Datex2JsonParser()
    license_attribution = "Monta ApS"
    # https://docs.public-api.monta.com/reference/get-afir-charge-points

    token_id = "monta_public_api"
    api_url = "https://public-api.monta.com/api/v1/afir/charge-points"
    token_url = "https://public-api.monta.com/api/v1/auth/token"
    refresh_url = "https://public-api.monta.com/api/v1/auth/refresh"

    def _get_monta_token(self):
        token = OAuthToken(id=self.id)
        response = requests.post(
            self.token_url,
            json={
                "clientId": os.environ.get("MONTA_PUBLIC_API_CLIENT_ID"),
                "clientSecret": os.environ.get("MONTA_PUBLIC_API_CLIENT_SECRET"),
            },
        ).json()
        token.access_token = response["accessToken"]
        token.refresh_token = response["refreshToken"]
        token.access_token_expires = datetime.datetime.fromisoformat(
            response["accessTokenExpirationDate"]
        )
        token.refresh_token_expires = datetime.datetime.fromisoformat(
            response["refreshTokenExpirationDate"]
        )
        token.save()
        return token

    def _refresh_monta_token(self, token):
        token = OAuthToken.objects.get(id=self.token_id)
        response = requests.post(
            self.refresh_url, json={"refreshToken": token.refresh_token}
        ).json()

        token.access_token = response["accessToken"]
        token.refresh_token = response["refreshToken"]
        token.access_token_expires = datetime.datetime.fromisoformat(
            response["accessTokenExpirationDate"]
        )
        token.refresh_token_expires = datetime.datetime.fromisoformat(
            response["refreshTokenExpirationDate"]
        )
        token.save()
        return token

    def _get_token(self):
        now = timezone.now()
        try:
            token = OAuthToken.objects.get(id=self.token_id)
        except OAuthToken.DoesNotExist:
            token = self._get_monta_token()

        if token.refresh_token_expires <= now:
            token = self._refresh_monta_token(token)
        elif token.access_token_expires <= now:
            token = self._get_monta_token()
        return token

    @abstractmethod
    @classproperty
    def country(self) -> str:
        pass

    def get_page(self, page: int, access_token: str, per_page: int = 1000) -> dict:
        response = requests.get(
            self.api_url,
            params={
                "country": self.country,
                "page": page,
                "perPage": per_page,
            },
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
        )
        response.raise_for_status()
        return response.json()

    def parse_all_pages(self):
        token = self._get_token()
        page = 1
        while True:
            root = self.get_page(page, token.access_token)
            yield from self.parser.parse(root)

            if root["meta"]["total"] <= root["meta"]["page"] * root["meta"]["perPage"]:
                break
            page += 1

    def pull_data(self):
        sites_datex = self.parse_all_pages()
        sync_chargers(
            self.id,
            (
                site.convert(
                    self.id,
                    self.license_attribution,
                    None,
                    self.country,
                )
                for site in sites_datex
            ),
        )


class Datex2DenmarkMontaDataSource(BaseMontaPublicDatex2DataSource):
    id = "denmark_monta"
    country = "DK"


class Datex2BelgiumMontaDataSource(BaseMontaPublicDatex2DataSource):
    id = "belgium_monta"
    country = "BE"
