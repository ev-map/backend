import requests

from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.irve.parser import parse_irve_csv
from evmap_backend.data_sources.sync import sync_chargers

DATA_URL = "https://proxy.transport.data.gouv.fr/resource/consolidation-transport-irve-statique"


class IrveFranceDataSource(DataSource):
    id = "irve_france"
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution = "data.gouv.fr, Open Licence 2.0"
    license_attribution_link = "https://www.data.gouv.fr/datasets/beta-base-nationale-des-points-de-recharge-pour-vehicules-electriques-en-france-irve"

    def pull_data(self):
        with requests.get(DATA_URL, stream=True) as response:
            response.raise_for_status()
            lines = response.iter_lines(decode_unicode=True)

            sites = parse_irve_csv(
                lines,
                self.id,
                self.license_attribution,
                self.license_attribution_link,
            )
            sync_chargers(self.id, sites)
