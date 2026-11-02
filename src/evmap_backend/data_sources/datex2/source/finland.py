import requests

from evmap_backend.data_sources.datex2.parser.json import Datex2JsonParser
from evmap_backend.data_sources.datex2.source import BaseDatex2DataSource


class Datex2FinlandDataSource(BaseDatex2DataSource):
    id = "fintraffic"
    parser = Datex2JsonParser(station_as_chargepoint=True)
    license_attribution = "Fintraffic / digitraffic.fi, CC-BY 4.0"
    license_attribution_link = "https://www.digitraffic.fi/en/terms-of-service/"
    # https://www.digitraffic.fi/en/road-traffic/afir/

    def get_data(self) -> str:
        response = requests.get(
            "https://afir.digitraffic.fi/api/charging-network/v1/locations/datex2-3.6",
        )
        response.raise_for_status()
        return response.text
