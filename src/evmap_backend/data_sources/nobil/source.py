import asyncio
import datetime
import os
import time

import aiohttp
import requests
from django.utils import timezone

from evmap_backend.chargers.models import Chargepoint
from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.models import UpdateState
from evmap_backend.data_sources.nobil.parser import parse_nobil_chargers
from evmap_backend.data_sources.sync import sync_chargers
from evmap_backend.realtime.models import CurrentStatus, PreviousStatus


class NobilDataSource(DataSource):
    id = "nobil"
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution = "NOBIL by Enova"
    license_attribution_link = "https://nobil.no/"

    def get_nobil_dump(self, fromdate: datetime.datetime | None = None):
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
            (
                site.convert(
                    self.id, self.license_attribution, self.license_attribution_link
                )
                for site in sites_nobil
            ),
            last_update is None,
        )


class NobilRealtimeDataSource(DataSource):
    id = "nobil_realtime"
    supported_data_types = [DataType.DYNAMIC]
    supported_update_methods = [UpdateMethod.STREAMING]
    license_attribution = "NOBIL by Enova"
    license_attribution_link = "https://nobil.no/"

    def _get_realtime_websocket_url(self):
        response = requests.post(
            "https://api.data.enova.no/nobil/real-time/v1/Realtime",
            headers={"x-api-key": os.environ["NOBIL_REALTIME_API_KEY"]},
        )
        return response.json()["accessToken"]

    async def _stream_data_async(self, url):
        updatestate_last_update = None
        async with aiohttp.ClientSession() as session, session.ws_connect(url) as ws:
            while True:
                msg = await asyncio.wait_for(ws.receive(), timeout=300)
                if msg.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSING,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                ):
                    break
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    evse_data = msg.json()
                    print(evse_data)

                    nobil_id_without_country = str(
                        int(evse_data["nobilId"].split("_")[1])
                    )
                    try:
                        chargepoint = await Chargepoint.objects.aget(
                            site__data_source="nobil",
                            site__id_from_source=nobil_id_without_country,
                            id_from_source=evse_data["evseUId"],
                        )

                        # Determine status value and timestamp
                        status_value = CurrentStatus.Status[evse_data["status"]]
                        ts = timezone.now()

                        # Save previous status
                        hist = PreviousStatus(
                            chargepoint=chargepoint,
                            status=status_value,
                            data_source=self.id,
                            license_attribution=self.license_attribution,
                            license_attribution_link=self.license_attribution_link,
                            timestamp=ts,
                        )
                        await hist.asave()

                        await CurrentStatus.objects.aupdate_or_create(
                            chargepoint=chargepoint,
                            defaults={
                                "status": status_value,
                                "timestamp": ts,
                                "data_source": self.id,
                                "license_attribution": self.license_attribution,
                                "license_attribution_link": self.license_attribution_link,
                            },
                        )

                        now = time.perf_counter()
                        if (
                            updatestate_last_update is None
                            or now - updatestate_last_update > 60
                        ):
                            # save the update state, but only once per minute
                            await UpdateState(data_source=self.id, push=True).asave()
                    except Chargepoint.DoesNotExist:
                        print("ignoring update")

    def stream_data(self):
        url = self._get_realtime_websocket_url()
        asyncio.run(self._stream_data_async(url))
