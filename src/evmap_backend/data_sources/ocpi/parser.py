from typing import Iterable

from tqdm import tqdm

from evmap_backend.data_sources.ocpi.model import OcpiLocation, OcpiTariff


class OcpiParser:
    def parse_locations(
        self, data: Iterable, status_only: bool = False
    ) -> Iterable[OcpiLocation]:
        for site in tqdm(data, disable=None):
            loc = OcpiLocation.model_validate(site)
            if loc is not None:
                yield loc

    def parse_tariffs(self, data: Iterable) -> Iterable[OcpiTariff]:
        for tariff in tqdm(data, disable=None):
            yield OcpiTariff.model_validate(tariff)
