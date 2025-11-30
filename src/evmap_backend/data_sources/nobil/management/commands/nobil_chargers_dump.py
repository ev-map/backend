import datetime as dt
import os
from typing import Optional

import dateutil.parser
import pytz
import requests
from django.contrib.gis.geos import Point
from django.core.management import BaseCommand
from django.db import transaction
from tqdm import tqdm

from evmap_backend.data_sources.nobil.models import (
    NobilChargerStation,
    NobilConnector,
    NobilUpdateState,
)

TIMEZONE = pytz.timezone("Europe/Berlin")

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class Command(BaseCommand):
    help = "Connects to Nobil API to extract charger information"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        last_update = NobilUpdateState.get_solo().last_update
        print(f"last update: {last_update}")

        now = dt.datetime.now()
        dump = get_nobil_dump(last_update)
        for data in tqdm(dump["chargerstations"]):
            csmd = data["csmd"]
            station_attrs = data["attr"]["st"]
            connectors = data["attr"]["conn"]

            lat, lon = [float(it) for it in csmd["Position"][1:-1].split(",")]
            charger = NobilChargerStation(
                id=csmd["id"],
                name=csmd["name"],
                location=Point(lon, lat),
                ocpi_id=none_to_blank(csmd["ocpidb_mapping_stasjon_id"]),
                street=csmd["Street"],
                house_number=csmd["House_number"],
                zip_code=csmd["Zipcode"],
                city=csmd["City"],
                municipality_id=csmd["Municipality_ID"],
                municipality=csmd["Municipality"],
                county_id=csmd["County_ID"],
                county=csmd["County"],
                description_of_location=none_to_blank(csmd["Description_of_location"]),
                owned_by=none_to_blank(csmd["Owned_by"]),
                operator=none_to_blank(csmd["Operator"]),
                num_chargepoints=csmd["Number_charging_points"],
                image=csmd["Image"] if csmd["Image"] != "no.image.svg" else "",
                available_chargepoints=csmd["Available_charging_points"],
                user_comment=none_to_blank(csmd["User_comment"]),
                contact_info=none_to_blank(csmd["Contact_info"]),
                created=dt.datetime.strptime(csmd["Created"], DATE_FORMAT).replace(
                    tzinfo=TIMEZONE
                ),
                updated=dt.datetime.strptime(csmd["Updated"], DATE_FORMAT).replace(
                    tzinfo=TIMEZONE
                ),
                station_status=csmd["Station_status"],
                land_code=csmd["Land_code"],
                international_id=csmd["International_id"],
                location_type=enumattr(station_attrs, 3),
                availability=enumattr(station_attrs, 2),
                open_24h=to_bool(enumattr(station_attrs, 24)),
                parking_fee=to_bool(enumattr(station_attrs, 7)),
                time_limit=to_bool(enumattr(station_attrs, 6)),
                real_time_information=to_bool(enumattr(station_attrs, 21)),
                public_funding=enumattr(station_attrs, 22),
            )

            with transaction.atomic():
                charger.save()
                NobilConnector.objects.filter(charging_station=charger).delete()

                for connector in connectors:
                    connector_attrs = connectors[connector]
                    connector = NobilConnector(
                        charging_station=charger,
                        vehicle_type=enumattr(connector_attrs, 17),
                        accessibility=enumattr(connector_attrs, 1),
                        energy_carrier=enumattr(connector_attrs, 26),
                        connector=enumattr(connector_attrs, 4),
                        charging_capacity=enumattr(connector_attrs, 5),
                        voltage=to_int(valattr(connector_attrs, 12)),
                        amperage=to_int(valattr(connector_attrs, 31)),
                        payment_method=enumattr(connector_attrs, 19),
                        timestamp=(
                            dateutil.parser.isoparse(valattr(connector_attrs, 16))
                            if "16" in connector_attrs
                            else None
                        ),
                        power_consumption=(
                            int(valattr(connector_attrs, 11))
                            if "11" in connector_attrs
                            else None
                        ),
                        connector_sensor_status=enumattr(connector_attrs, 10),
                        connector_error_status=enumattr(connector_attrs, 9),
                        connector_status=enumattr(connector_attrs, 8),
                        evse_uid=none_to_blank(valattr(connector_attrs, 27)),
                        fixed_cable=to_bool(enumattr(connector_attrs, 25)),
                        evse_id=none_to_blank(valattr(connector_attrs, 28)),
                        connector_id=none_to_blank(valattr(connector_attrs, 29)),
                        charge_mode=enumattr(connector_attrs, 20),
                        reservable=to_bool(enumattr(connector_attrs, 18)),
                        manufacturer=none_to_blank(valattr(connector_attrs, 23)),
                    )
                    connector.save()

        state = NobilUpdateState.get_solo()
        state.last_update = now
        state.save()


def get_nobil_dump(fromdate: Optional[dt.datetime] = None):
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


def enumattr(attrs, type):
    if str(type) in attrs:
        return int(attrs[str(type)]["attrvalid"])
    else:
        return None


def valattr(attrs, type):
    if str(type) in attrs:
        return attrs[str(type)]["attrval"]
    else:
        return None


def none_to_blank(val: Optional[str]) -> str:
    if val is None:
        return ""
    else:
        return val


def to_int(val: Optional[str]) -> Optional[int]:
    if val is None or not val.isnumeric():
        return None
    else:
        return int(val)


def to_bool(val: Optional[int]) -> Optional[bool]:
    if val is None:
        return None
    else:
        return val == 1
