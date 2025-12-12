import asyncio
import datetime
import os
from typing import List, Optional

import aiohttp
import requests
from asgiref.sync import sync_to_async

from evmap_backend.chargers.models import Chargepoint
from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.models import UpdateState
from evmap_backend.data_sources.nobil.parser import parse_nobil_chargers
from evmap_backend.realtime.models import RealtimeStatus
from evmap_backend.sync import sync_chargers


class NobilDataSource(DataSource):
    @property
    def id(self) -> str:
        return "nobil"

    @property
    def supported_data_types(self) -> List[DataType]:
        return [DataType.STATIC]

    @property
    def supported_update_methods(self) -> List[UpdateMethod]:
        return [UpdateMethod.PULL]

    def get_nobil_dump(self, fromdate: Optional[datetime.datetime] = None):
        response = requests.get(
            "https://nobil.no/api/server/datadump.php",
            params={
                "apikey": os.environ["NOBIL_API_KEY"],
                "format": "json",
                "file": "false",
                "fromdate": fromdate.date() if fromdate is not None else None,
            },
        )
        return response.json()

    def pull_data(self):
        update_state = UpdateState.objects.filter(data_source=self.id).first()
        last_update = update_state.last_update if update_state else None
        print(f"last update: {last_update}")

        dump = self.get_nobil_dump(last_update)
        sites_nobil = parse_nobil_chargers(dump)
        sync_chargers(
            self.id,
            (site.convert(self.id) for site in sites_nobil),
            last_update is None,
        )


class NobilRealtimeDataSource(DataSource):
    @property
    def id(self) -> str:
        return "nobil_realtime"

    @property
    def supported_data_types(self) -> List[DataType]:
        return [DataType.DYNAMIC]

    @property
    def supported_update_methods(self) -> List[UpdateMethod]:
        return [UpdateMethod.STREAMING]

    def _get_realtime_websocket_url(self):
        response = requests.post(
            "https://api.data.enova.no/nobil/real-time/v1/Realtime",
            headers={"x-api-key": os.environ["NOBIL_REALTIME_API_KEY"]},
        )
        return response.json()["accessToken"]

    async def _stream_data_async(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        evse_data = msg.json()
                        print(evse_data)

                        nobil_id_without_country = str(
                            int(evse_data["nobilId"].split("_")[1])
                        )
                        try:
                            chargepoint = await sync_to_async(Chargepoint.objects.get)(
                                site__data_source="nobil",
                                site__id_from_source=nobil_id_without_country,
                                id_from_source=evse_data["evseUId"],
                            )

                            obj = RealtimeStatus(
                                chargepoint=chargepoint,
                                status=RealtimeStatus.Status[evse_data["status"]],
                                data_source=self.id,
                            )
                            await sync_to_async(obj.save)()
                        except Chargepoint.DoesNotExist:
                            print(f"ignoring update")
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        break

    def stream_data(self):
        url = self._get_realtime_websocket_url()
        asyncio.run(self._stream_data_async(url))
