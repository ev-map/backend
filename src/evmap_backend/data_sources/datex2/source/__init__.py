"""
DATEX-II-based data sources.
The actual source implementations live in submodules here. They are organized in the following manner:

If multiple sources can reuse similar implementations (e.g., because data from multiple sources is served through
the same data access platform) they go into a common module. This may be named after the platform (e.g., Mobilithek),
the country operating the platform (e.g., Latvia), or the third party serving APIs for multiple countries
(e.g., Eco-Movement, Monta, Spirii). If no reuse is possible, group the remaining sources by country.
"""

import logging
from abc import abstractmethod

from django.utils.functional import classproperty

from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.datex2.parser.xml import Datex2XmlParser
from evmap_backend.data_sources.sync import sync_chargers, sync_statuses

logger = logging.getLogger(__name__)


class NotModifiedError(Exception):
    pass


class BaseDatex2DataSource(DataSource):
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution_link: str | None = None
    parser = Datex2XmlParser()
    default_timezone = None
    default_country = None

    @abstractmethod
    def get_data(self) -> str:
        """Get the data from the data source"""

    @property
    def static_data_source(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    @classproperty
    def license_attribution(self) -> str:
        pass

    def pull_data(self):
        try:
            root = self.get_data()
            self._parse_data(root)
        except NotModifiedError:
            logger.info("Not modified")

    def process_push(self, body: bytes):
        root = body.decode("utf-8")
        self._parse_data(root)

    def _parse_data(self, root: str):
        if self.supported_data_types == [DataType.STATIC]:
            sites_datex = self.parser.parse(root)
            sync_chargers(
                self.id,
                (
                    site.convert(
                        self.id,
                        self.license_attribution,
                        self.license_attribution_link,
                        self.default_country,
                    )
                    for site in sites_datex
                ),
            )
        elif self.supported_data_types == [DataType.DYNAMIC]:
            statuses_datex = self.parser.parse_status(
                root,
                default_timezone=self.default_timezone,
            )
            sync_statuses(
                self.id,
                self.static_data_source,
                (
                    s
                    for status in statuses_datex
                    for s in status.convert(
                        self.id, self.license_attribution, self.license_attribution_link
                    )
                ),
            )
        else:
            raise NotImplementedError()
