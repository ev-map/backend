import os

import requests

from evmap_backend.data_sources.datex2.source import BaseDatex2DataSource


class Datex2DenmarkOkDataSource(BaseDatex2DataSource):
    id = "denmark_ok"
    license_attribution = "OK A.M.B.A."
    token = os.environ.get("OK_DENMARK_TOKEN")
    # https://du-portal-ui.dataudveksler.app.vd.dk/data/1096/overview

    def get_data(self) -> str:
        response = requests.get(
            f"https://ocpi-emobility.okcloud.dk/datex/locations?token={self.token}",
        )
        response.raise_for_status()
        return response.text


class Datex2DenmarkTotalEnergiesDataSource(BaseDatex2DataSource):
    id = "denmark_totalenergies"
    license_attribution = "TotalEnergies Marketing Danmark A/S"
    # https://du-portal-ui.dataudveksler.app.vd.dk/data/1152/overview

    def get_data(self) -> str:
        response = requests.get(
            "https://api-te.bluebell.dk/datex2/v3/TEE/EnergyInfrastructureTablePublication",
        )
        response.raise_for_status()
        return response.text
