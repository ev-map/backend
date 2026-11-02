import requests

from evmap_backend.data_sources.datex2.source import BaseDatex2DataSource


class Datex2SpainDataSource(BaseDatex2DataSource):
    id = "spain"
    license_attribution = "Dirección General de Tráfico, CC-BY 4.0"
    license_attribution_link = (
        "https://nap.dgt.es/dataset/puntos-de-recarga-electrica-para-vehiculos"
    )
    default_country = "ES"
    # https://nap.dgt.es/dataset/puntos-de-recarga-electrica-para-vehiculos

    def get_data(self) -> str:
        response = requests.get(
            "https://infocar.dgt.es/datex2/v3/miterd/EnergyInfrastructureTablePublication/electrolineras.xml",
        )
        response.raise_for_status()
        return response.text
