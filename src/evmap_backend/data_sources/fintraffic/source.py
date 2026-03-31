import json
import logging
import time

import paho.mqtt.client as mqtt
from django.utils import timezone

from evmap_backend.chargers.fields import normalize_evseid
from evmap_backend.chargers.models import Chargepoint
from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.models import UpdateState
from evmap_backend.realtime.models import RealtimeStatus

logger = logging.getLogger(__name__)


class FintrafficRealtimeDataSource(DataSource):
    id = "fintraffic_realtime"
    supported_data_types = [DataType.DYNAMIC]
    supported_update_methods = [UpdateMethod.STREAMING]
    license_attribution = "Fintraffic / digitraffic.fi, CC-BY 4.0"
    license_attribution_link = "https://www.digitraffic.fi/en/terms-of-service/"

    def __init__(self):
        self.updatestate_last_update = None

    def _on_connect(self, client, userdata, flags, rc, props):
        logger.info("Connected")
        client.subscribe("status-v1/#")

    def _on_disconnect(self, client, userdata, flags, rc, props):
        logger.info(f"Disconnected with reason code: {rc}")

    def _on_message(self, client, userdata, msg):
        logger.debug(f"Received message: {msg.topic} {msg.payload}")

        topic = msg.topic
        if not topic.startswith("status-v1/"):
            return

        evseid = normalize_evseid(topic.split("/")[-1])
        evse_data = json.loads(msg.payload.decode("utf-8"))

        try:
            chargepoint = Chargepoint.objects.get(
                site__data_source="fintraffic", evseid=evseid
            )

            current_status = (
                RealtimeStatus.objects.filter(chargepoint=chargepoint)
                .order_by("-timestamp")
                .first()
            )

            if (
                current_status is not None
                and current_status.status == RealtimeStatus.Status[evse_data["status"]]
            ):
                logger.debug("ignoring update, no change")
                return

            RealtimeStatus(
                chargepoint=chargepoint,
                status=RealtimeStatus.Status[evse_data["status"]],
                data_source=self.id,
                license_attribution=self.license_attribution,
                license_attribution_link=self.license_attribution_link,
                timestamp=timezone.now(),
            ).save()

            now = time.perf_counter()
            if (
                self.updatestate_last_update is None
                or now - self.updatestate_last_update > 60
            ):
                # save the update state, but only once per minute
                UpdateState(data_source=self.id, push=True).save()
        except Chargepoint.DoesNotExist:
            logger.debug(f"ignoring update, chargepoint {evseid} does not exist")

    def stream_data(self):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, transport="websockets")
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        client.tls_set()
        client.connect("afir.digitraffic.fi", 443, 60)
        client.loop_forever()
