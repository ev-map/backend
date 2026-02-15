import asyncio
import datetime
import os
import time
from typing import List, Optional

import aiohttp
import requests
from asgiref.sync import sync_to_async
from django.utils import timezone

from evmap_backend.chargers.models import Chargepoint
from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.models import UpdateState
from evmap_backend.data_sources.nobil.parser import parse_nobil_chargers
from evmap_backend.realtime.models import RealtimeStatus
from evmap_backend.sync import sync_chargers


class OpendataSwissDataSource(DataSource):
    id = "opendata_swiss"
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution = "ich-tanke-strom.ch"
    license_attribution_link = "https://ich-tanke-strom.ch"

    def pull_data(self):
        url = "https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
        pass


class OpendataSwissRealtimeDataSource(DataSource):
    id = "opendata_swiss_realtime"
    supported_data_types = [DataType.DYNAMIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution = "ich-tanke-strom.ch"
    license_attribution_link = "https://ich-tanke-strom.ch"

    def pull_data(self):
        url = "https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/status/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
        pass
