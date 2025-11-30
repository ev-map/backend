import asyncio
import os

import aiohttp
import requests
from asgiref.sync import sync_to_async
from django.core.management import BaseCommand

from evmap_backend.data_sources.nobil.models import NobilRealtimeData


class Command(BaseCommand):
    help = "Connects to Nobil WebSocket API to receive realtime updates about charger availability"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        url = get_nobil_realtime_websocket_url()
        asyncio.run(nobil_realtime_listener(url))


def get_nobil_realtime_websocket_url():
    response = requests.post(
        "https://api.data.enova.no/nobil/real-time/v1/Realtime",
        headers={"x-api-key": os.environ["NOBIL_REALTIME_API_KEY"]},
    )
    return response.json()["accessToken"]


async def nobil_realtime_listener(url):
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    evse_data = msg.json()
                    print(evse_data)

                    obj = NobilRealtimeData(
                        nobil_id=evse_data["nobilId"],
                        evse_uid=evse_data["evseUId"],
                        status=NobilRealtimeData.Status[evse_data["status"]],
                    )
                    await sync_to_async(obj.save)()
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
