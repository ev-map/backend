import datetime as dt
import os
from collections import defaultdict

import requests
from django.contrib.gis.geos import Point
from django.utils import timezone
from tqdm import tqdm

from evmap_backend.chargers.fields import normalize_evseid
from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector, Network
from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.monta.models import MontaTokens
from evmap_backend.realtime.models import RealtimeStatus
from evmap_backend.sync import sync_chargers, sync_statuses

API_URL = "https://partner-api.monta.com/api/v1/afir/charge-points"
TOKEN_URL = "https://partner-api.monta.com/api/v1/auth/token"
REFRESH_URL = "https://partner-api.monta.com/api/v1/auth/refresh"

connector_mapping = {
    "type1": Connector.ConnectorTypes.TYPE_1,
    "type2": Connector.ConnectorTypes.TYPE_2,
    "ccs": Connector.ConnectorTypes.CCS_TYPE_2,
    "ccs1": Connector.ConnectorTypes.CCS_TYPE_1,
    "chademo": Connector.ConnectorTypes.CHADEMO,
    "schuko": Connector.ConnectorTypes.SCHUKO,
    "nacs": Connector.ConnectorTypes.NACS,
}

country_map = {"Germany": "DE"}


def get_monta_token():
    response = requests.post(
        TOKEN_URL,
        json={
            "clientId": os.environ.get("MONTA_CLIENT_ID"),
            "clientSecret": os.environ.get("MONTA_CLIENT_SECRET"),
        },
    )
    return response.json()


def refresh_monta_token(refresh_token):
    response = requests.post(REFRESH_URL, json={"refreshToken": refresh_token})
    return response.json()


def get_monta_data(access_token, after=None):
    response = requests.get(
        API_URL,
        params={
            "after": after,
            "countryId": 196,
            # TODO: this only gets the data for Germany. If we want more than this, we need to ask Monta to increase
            # our request limit to more than 100 per 10 minutes
        },
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )
    response.raise_for_status()
    return response.json()


def get_all_monta_chargers(access_token):
    root = get_monta_data(access_token)
    for charger in root["data"]:
        yield charger

    while root["meta"]["after"] is not None:
        root = get_monta_data(access_token, after=root["meta"]["after"])
        for charger in root["data"]:
            yield charger


status_map = {
    "available": RealtimeStatus.Status.AVAILABLE,
    "busy": RealtimeStatus.Status.CHARGING,
    "busy-blocked": RealtimeStatus.Status.BLOCKED,
    "busy-charging": RealtimeStatus.Status.CHARGING,
    "busy-non-charging": RealtimeStatus.Status.BLOCKED,
    "busy-non-released": RealtimeStatus.Status.BLOCKED,
    "busy-reserved": RealtimeStatus.Status.RESERVED,
    "busy-scheduled": RealtimeStatus.Status.RESERVED,
    "error": RealtimeStatus.Status.OUTOFORDER,
    "disconnected": RealtimeStatus.Status.UNKNOWN,
    "passive": RealtimeStatus.Status.UNKNOWN,
    "maintenance": RealtimeStatus.Status.OUTOFORDER,
    "exempt": RealtimeStatus.Status.UNKNOWN,
}


def convert_monta_data(chargers_by_location, source, license_attribution):
    for location in chargers_by_location:
        evses = chargers_by_location[location]
        site = ChargingSite(
            data_source=source,
            license_attribution=license_attribution,
            id_from_source=location,
            name=f"{evses[0]['roamingOperatorName']} {evses[0]['location']['address']['address1']}",
            location=Point(
                evses[0]["location"]["coordinates"]["longitude"],
                evses[0]["location"]["coordinates"]["latitude"],
            ),
            street=evses[0]["location"]["address"]["address1"],
            zipcode=evses[0]["location"]["address"]["zip"],
            city=evses[0]["location"]["address"]["city"],
            country=country_map[evses[0]["location"]["address"]["country"]],
            network=Network.objects.get_or_create(
                evse_operator_id="DKMON", defaults=dict(name="Monta")
            )[0],
            operator=evses[0]["roamingOperatorName"],
        )

        chargepoints = []
        statuses = []
        for evse in evses:
            chargepoint = Chargepoint(
                id_from_source=str(evse["id"]), evseid=normalize_evseid(evse["evseId"])
            )
            connectors = [
                Connector(
                    connector_type=connector_mapping[connector["identifier"]],
                    max_power=evse["maxKw"] * 1000,
                )
                for connector in evse["connectors"]
            ]
            chargepoints.append((chargepoint, connectors))
            status = RealtimeStatus(
                chargepoint=chargepoint,
                status=status_map[evse["state"]],
                timestamp=timezone.now(),
                data_source=source,
                license_attribution=license_attribution,
            )
            statuses.append((location, status))

        yield site, chargepoints, statuses


class MontaDataSource(DataSource):
    id = "monta"
    supported_data_types = [DataType.STATIC, DataType.DYNAMIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution = "Monta ApS"
    # https://docs.partner-api.monta.com/docs/afir-access
    # Rate limit: 100 requests per 10 minutes

    def pull_data(self):
        tokens = MontaTokens.get_solo()
        now = timezone.now()
        if tokens.refresh_token_expires <= now:
            response = get_monta_token()
            tokens.access_token = response["accessToken"]
            tokens.refresh_token = response["refreshToken"]
            tokens.access_token_expires = dt.datetime.fromisoformat(
                response["accessTokenExpirationDate"]
            )
            tokens.refresh_token_expires = dt.datetime.fromisoformat(
                response["refreshTokenExpirationDate"]
            )
            tokens.save()
        elif tokens.access_token_expires <= now:
            response = refresh_monta_token(tokens.refresh_token)
            tokens.access_token = response["accessToken"]
            tokens.refresh_token = response["refreshToken"]
            tokens.access_token_expires = dt.datetime.fromisoformat(
                response["accessTokenExpirationDate"]
            )
            tokens.refresh_token_expires = dt.datetime.fromisoformat(
                response["refreshTokenExpirationDate"]
            )
            tokens.save()

        chargers_by_location = defaultdict(list)
        for charger in tqdm(get_all_monta_chargers(access_token=tokens.access_token)):
            chargers_by_location[charger["location"]["addressLabel"]].append(charger)

        sites = list(
            convert_monta_data(chargers_by_location, self.id, self.license_attribution)
        )
        sync_chargers(
            self.id, ((site, chargepoints) for site, chargepoints, statuses in sites)
        )
        sync_statuses(
            self.id,
            self.id,
            (status for site, chargepoints, statuses in sites for status in statuses),
        )
