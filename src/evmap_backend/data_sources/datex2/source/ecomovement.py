import os
import re
from abc import abstractmethod

import requests
from django.utils.functional import classproperty

from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.datex2.parser.json import Datex2JsonParser
from evmap_backend.data_sources.datex2.source import BaseDatex2DataSource
from evmap_backend.data_sources.sync import SyncPage, sync_chargers_and_statuses

link_regex = re.compile('<([^>]+)>; rel="next"')


class Datex2LuxembourgEcoMovementDataSource(BaseDatex2DataSource):
    id = "luxembourg_ecomovement"
    token = os.environ.get("ECOMOVEMENT_LUXEMBOURG_TOKEN")
    # https://data.public.lu/en/datasets/bornes-de-chargement-publiques-pour-voitures-electriques-du-plusieurs-operateurs-1/

    def get_data(self) -> str:
        response = requests.get(
            "https://api.eco-movement.com/api/nap/datexii/locations",
            params={
                "token": self.token,
            },
        )
        response.raise_for_status()
        return response.text


class BaseEcoMovementNapDatex2DataSource(DataSource):
    license_attribution = "Eco-Movement BV"
    parser = Datex2JsonParser()
    supported_data_types = [DataType.STATIC, DataType.DYNAMIC]
    supported_update_methods = [UpdateMethod.PULL]
    # https://developers.eco-movement.com/v5/docs/eco-movement-data-api-datex

    @abstractmethod
    @classproperty
    def token(self) -> str:
        pass

    @abstractmethod
    @classproperty
    def base_url(self) -> str:
        pass

    def parse_all_pages(self):
        next_url = f"{self.base_url}/datex2/v1/locations"
        while next_url is not None:
            root, next_url = self.get_page(next_url)
            yield SyncPage(
                sites=(
                    site.convert(
                        self.id,
                        self.license_attribution,
                        None,
                        None,
                    )
                    for site in self.parser.parse(root)
                ),
                statuses=(
                    s
                    for status in self.parser.parse_status(root)
                    for s in status.convert(
                        self.id,
                        self.license_attribution,
                        None,
                    )
                ),
            )

    def pull_data(self):
        sync_chargers_and_statuses(
            self.id,
            self.parse_all_pages(),
        )

    def get_page(self, url) -> str:
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
            },
        )
        response.raise_for_status()
        link_header = response.headers.get("Link")
        if link_header:
            link = link_regex.match(link_header).group(1)
        else:
            link = None
        return response.text, link


class Datex2DenmarkEcoMovementDataSource(BaseEcoMovementNapDatex2DataSource):
    id = "denmark_ecomovement"
    token = os.environ.get("ECOMOVEMENT_DENMARK_TOKEN")
    base_url = "https://nap-dk.eco-movement.com"
    # https://du-portal-ui.dataudveksler.app.vd.dk/data/1170/overview


class Datex2BelgiumEcoMovementDataSource(BaseEcoMovementNapDatex2DataSource):
    id = "belgium_ecomovement"
    token = os.environ.get("ECOMOVEMENT_BELGIUM_TOKEN")
    base_url = "https://nap-be.eco-movement.com"
    # https://transportdata.be/de/dataset/public-charging-infrastructure-static-dataset-selected-cpos-datex-ii
