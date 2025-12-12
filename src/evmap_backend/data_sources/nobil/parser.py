import datetime
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Iterable, List, Optional, Tuple

import dateutil
import pytz
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from tqdm import tqdm

from evmap_backend.chargers.fields import normalize_evseid, validate_evseid
from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector
from evmap_backend.helpers.database import none_to_blank

TIMEZONE = pytz.timezone("Europe/Berlin")
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class NobilConnector:
    class VehicleType(IntEnum):
        E_ALL = 15
        E_CARS_VANS = 1
        E_VANS = 6
        E_TRUCKS = 10
        E_BUSES = 13
        E_BUSES_TRUCKS = 14
        E_BOATS = 20
        E_CARS_VANS_BOATS = 22
        H_ALL = 7
        H_CARS = 8
        H_TRUCKS = 9
        E_H_CARS_VANS = 12
        BIOGAS = 16
        ALL = 11

    class Accessibility(IntEnum):
        OPEN = 1
        STANDARD_KEY = 2
        OTHER = 3
        RFID = 4
        PAYMENT = 5
        CELLULAR_PHONE = 6

    class EnergyCarrier(IntEnum):
        ELECTRICITY = 1
        HYDROGEN = 2
        BIOGAS = 3

    class Connector(IntEnum):
        TYPE_1 = 31
        TYPE_2 = 32
        CHADEMO = 30
        CCS = 39
        TESLA = 40
        TYPE_2_SCHUKO = 50
        TYPE_1_TYPE_2 = 60
        MCS = 87
        HYDROGEN = 70
        BIOGAS = 82
        UNSPECIFIED = 0

    class ChargingCapacity(IntEnum):
        AC_3_6 = 7
        AC_7_4 = 8
        AC_11 = 10
        DC_20 = 19
        AC_22 = 11
        DC_30 = 37
        AC_43 = 12
        DC_62_5 = 38
        DC_50 = 13
        DC_75 = 29
        DC_100 = 23
        DC_135 = 22
        DC_150 = 24
        DC_175 = 41
        DC_180 = 42
        DC_200 = 32
        DC_225 = 30
        DC_250 = 31
        DC_300 = 33
        DC_350 = 25
        DC_400 = 36
        DC_500 = 39
        DC_600 = 43
        DC_700 = 44
        DC_800 = 45
        UNSPECIFIED = 0
        AC_11_ALT = 16
        AC_22_ALT = 17
        AC_43_ALT = 18
        H_350 = 26
        H_700 = 27
        CBG = 34
        LBG = 35

    class PaymentMethod(IntEnum):
        CELLPHONE = 1
        BANK_CARD = 2
        MISCELLANEOUS = 10
        CELLPHONE_CHARGING_CARD = 20
        BANK_CARD_CHARGING_CARD = 21
        BANK_CARD_CHARGING_CARD_CELLPHONE = 25

    class ConnectorSensorStatus(IntEnum):
        VACANT = 0
        BUSY = 1

    class ConnectorErrorStatus(IntEnum):
        IN_SERVICE = 0
        OUT_OF_SERVICE = 1

    class ConnectorStatus(IntEnum):
        VACANT = 0
        BUSY = 1
        RESERVED = 2

    class ChargeMode(IntEnum):
        MODE_1 = 1
        MODE_2 = 2
        MODE_3 = 3
        MODE_4 = 4

    vehicle_type: Optional[VehicleType]
    accessibility: Optional[Accessibility]
    energy_carrier: Optional[EnergyCarrier]
    connector: Optional[Connector]
    charging_capacity: Optional[ChargingCapacity]
    voltage: Optional[int]
    amperage: Optional[int]
    payment_method: Optional[PaymentMethod]
    timestamp: Optional[datetime.datetime]
    power_consumption: Optional[int]
    connector_sensor_status: Optional[ConnectorSensorStatus]
    connector_error_status: Optional[ConnectorErrorStatus]
    connector_status: Optional[ConnectorStatus]
    evse_uid: Optional[str]
    fixed_cable: Optional[bool]
    evse_id: Optional[str]
    connector_id: Optional[str]
    charge_mode: Optional[ChargeMode]
    reservable: Optional[bool]
    manufacturer: Optional[str]

    def convert(self) -> List[Connector]:
        if self.connector in [
            NobilConnector.Connector.BIOGAS,
            NobilConnector.Connector.HYDROGEN,
        ]:
            # skip non-EV connectors
            return []
        if self.connector == NobilConnector.Connector.TYPE_2_SCHUKO:
            return [
                Connector(
                    connector_type=Connector.ConnectorTypes.SCHUKO,
                    max_power=2.3,
                ),
                Connector(
                    connector_type=Connector.ConnectorTypes.TYPE_2,
                    max_power=self.power_consumption,
                ),
            ]
        if self.connector == NobilConnector.Connector.TYPE_1_TYPE_2:
            return [
                Connector(
                    connector_type=Connector.ConnectorTypes.TYPE_1,
                    max_power=self.power_consumption,
                ),
                Connector(
                    connector_type=Connector.ConnectorTypes.TYPE_2,
                    max_power=self.power_consumption,
                ),
            ]

        return [
            Connector(
                connector_type=connector_mapping.get(
                    self.connector, Connector.ConnectorTypes.OTHER
                ),
                max_power=charging_capacity_mapping.get(self.charging_capacity, 0),
            )
        ]


connector_mapping = {
    NobilConnector.Connector.TYPE_1: Connector.ConnectorTypes.TYPE_1,
    NobilConnector.Connector.TYPE_2: Connector.ConnectorTypes.TYPE_2,
    NobilConnector.Connector.CHADEMO: Connector.ConnectorTypes.CHADEMO,
    NobilConnector.Connector.CCS: Connector.ConnectorTypes.CCS_TYPE_2,
    NobilConnector.Connector.TESLA: Connector.ConnectorTypes.TESLA_SUPERCHARGER_EU,
    NobilConnector.Connector.MCS: Connector.ConnectorTypes.MCS,
}

charging_capacity_mapping = {
    NobilConnector.ChargingCapacity.AC_3_6: 3_600,
    NobilConnector.ChargingCapacity.AC_7_4: 7_400,
    NobilConnector.ChargingCapacity.AC_11: 11_000,
    NobilConnector.ChargingCapacity.DC_20: 20_000,
    NobilConnector.ChargingCapacity.AC_22: 22_000,
    NobilConnector.ChargingCapacity.DC_30: 30_000,
    NobilConnector.ChargingCapacity.AC_43: 43_000,
    NobilConnector.ChargingCapacity.DC_50: 50_000,
    NobilConnector.ChargingCapacity.DC_75: 75_000,
    NobilConnector.ChargingCapacity.DC_100: 100_000,
    NobilConnector.ChargingCapacity.DC_135: 135_000,
    NobilConnector.ChargingCapacity.DC_150: 150_000,
    NobilConnector.ChargingCapacity.DC_175: 175_000,
    NobilConnector.ChargingCapacity.DC_200: 200_000,
    NobilConnector.ChargingCapacity.DC_225: 225_000,
    NobilConnector.ChargingCapacity.DC_250: 250_000,
    NobilConnector.ChargingCapacity.DC_300: 300_000,
    NobilConnector.ChargingCapacity.DC_350: 350_000,
    NobilConnector.ChargingCapacity.DC_400: 400_000,
    NobilConnector.ChargingCapacity.DC_500: 500_000,
    NobilConnector.ChargingCapacity.DC_600: 600_000,
    NobilConnector.ChargingCapacity.DC_700: 700_000,
    NobilConnector.ChargingCapacity.DC_800: 800_000,
    NobilConnector.ChargingCapacity.AC_11_ALT: 11_000,
    NobilConnector.ChargingCapacity.AC_22_ALT: 22_000,
    NobilConnector.ChargingCapacity.AC_43_ALT: 43_000,
}


@dataclass
class NobilChargerStation:
    class LocationType(IntEnum):
        STREET = 1
        CAR_PARK = 2
        AIRPORT = 3
        SHOPPING_CENTER = 4
        TRANSPORT_HUB = 5
        HOTELS_RESTAURANTS = 6
        GAS_STATION = 7

    class Availability(IntEnum):
        PUBLIC = 1
        VISITORS = 2
        EMPLOYEES = 3
        BY_APPOINTMENT = 4
        RESIDENTS = 5

    class PublicFunding(IntEnum):
        OSLO_KOMMUNE = 1
        TRANSNOVA = 2
        OTHER = 3
        NONE = 4
        KLIMASTEGET = 5
        TRAFIKKVERKET = 6

    id: int
    name: str
    location: tuple[float, float]  # (longitude, latitude)
    street: str
    house_number: str
    zip_code: str
    city: str
    municipality_id: str
    municipality: str
    county_id: str
    county: str
    num_chargepoints: int
    available_chargepoints: int
    created: datetime.datetime
    updated: datetime.datetime
    station_status: int
    land_code: str
    international_id: str
    location_type: LocationType
    availability: Availability
    open_24h: bool
    parking_fee: bool
    time_limit: bool
    real_time_information: bool
    public_funding: PublicFunding
    ocpi_id: Optional[str]
    description_of_location: Optional[str]
    owned_by: Optional[str]
    operator: Optional[str]
    image: str
    user_comment: Optional[str]
    contact_info: Optional[str]
    connectors: List[NobilConnector]

    def convert(
        self, data_source: str
    ) -> Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]]:
        site = ChargingSite(
            data_source=data_source,
            id_from_source=str(self.id),
            name=self.name,
            location=Point(*self.location),
            operator=none_to_blank(self.operator),
            street=none_to_blank(self.street),
            zipcode=none_to_blank(self.zip_code),
            city=none_to_blank(self.city),
            country=self.land_code,
        )

        # group connectors by EVSE UID and EVSEID
        evse_dict = defaultdict(list)
        for con in self.connectors:
            if con.evse_id is None or con.evse_uid is None:
                continue

            # normalize and validate EVSEID
            evseid = normalize_evseid(con.evse_id)
            try:
                validate_evseid(evseid)
            except ValidationError:
                evseid = ""
            evse_dict[(con.evse_uid, evseid)].append(con)

        chargepoints = [
            (
                Chargepoint(site=site, id_from_source=evse_uid, evseid=evseid),
                [c for con in connectors for c in con.convert()],
            )
            for (evse_uid, evseid), connectors in evse_dict.items()
        ]
        return site, chargepoints


@dataclass
class NobilRealtimeData:
    class RealtimeStatus(str, Enum):
        AVAILABLE = "AVAILABLE"
        BLOCKED = "BLOCKED"
        CHARGING = "CHARGING"
        INOPERATIVE = "INOPERATIVE"
        OUTOFORDER = "OUTOFORDER"
        PLANNED = "PLANNED"
        REMOVED = "REMOVED"
        RESERVED = "RESERVED"
        UNKNOWN = "UNKNOWN"

    nobil_id: str
    evse_uid: str
    status: RealtimeStatus
    timestamp: datetime.datetime


def enumattr(attrs, type, enum_type):
    if str(type) in attrs:
        return enum_type(int(attrs[str(type)]["attrvalid"]))
    else:
        return None


def valattr(attrs, type):
    if str(type) in attrs:
        return attrs[str(type)]["attrval"]
    else:
        return None


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


def parse_nobil_chargers(json_data) -> Iterable[NobilChargerStation]:
    for data in tqdm(json_data["chargerstations"]):
        csmd = data["csmd"]

        station_attrs = data["attr"]["st"]
        connectors = data["attr"]["conn"]

        lat, lon = [float(it) for it in csmd["Position"][1:-1].split(",")]
        charger = NobilChargerStation(
            id=csmd["id"],
            name=csmd["name"],
            location=(lon, lat),
            ocpi_id=csmd["ocpidb_mapping_stasjon_id"],
            street=csmd["Street"],
            house_number=csmd["House_number"],
            zip_code=csmd["Zipcode"],
            city=csmd["City"],
            municipality_id=csmd["Municipality_ID"],
            municipality=csmd["Municipality"],
            county_id=csmd["County_ID"],
            county=csmd["County"],
            description_of_location=csmd["Description_of_location"],
            owned_by=csmd["Owned_by"],
            operator=csmd["Operator"],
            num_chargepoints=csmd["Number_charging_points"],
            image=csmd["Image"] if csmd["Image"] != "no.image.svg" else "",
            available_chargepoints=csmd["Available_charging_points"],
            user_comment=csmd["User_comment"],
            contact_info=csmd["Contact_info"],
            created=datetime.datetime.strptime(csmd["Created"], DATE_FORMAT).replace(
                tzinfo=TIMEZONE
            ),
            updated=datetime.datetime.strptime(csmd["Updated"], DATE_FORMAT).replace(
                tzinfo=TIMEZONE
            ),
            station_status=csmd["Station_status"],
            land_code=csmd["Land_code"],
            international_id=csmd["International_id"],
            location_type=enumattr(station_attrs, 3, NobilChargerStation.LocationType),
            availability=enumattr(station_attrs, 2, NobilChargerStation.Availability),
            open_24h=enumattr(station_attrs, 24, bool),
            parking_fee=enumattr(station_attrs, 7, bool),
            time_limit=enumattr(station_attrs, 6, bool),
            real_time_information=enumattr(station_attrs, 21, bool),
            public_funding=enumattr(
                station_attrs, 22, NobilChargerStation.PublicFunding
            ),
            connectors=[
                NobilConnector(
                    vehicle_type=enumattr(
                        connector_attrs, 17, NobilConnector.VehicleType
                    ),
                    accessibility=enumattr(
                        connector_attrs, 1, NobilConnector.Accessibility
                    ),
                    energy_carrier=enumattr(
                        connector_attrs, 26, NobilConnector.EnergyCarrier
                    ),
                    connector=enumattr(connector_attrs, 4, NobilConnector.Connector),
                    charging_capacity=enumattr(
                        connector_attrs, 5, NobilConnector.ChargingCapacity
                    ),
                    voltage=to_int(valattr(connector_attrs, 12)),
                    amperage=to_int(valattr(connector_attrs, 31)),
                    payment_method=enumattr(
                        connector_attrs, 19, NobilConnector.PaymentMethod
                    ),
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
                    connector_sensor_status=enumattr(
                        connector_attrs, 10, NobilConnector.ConnectorSensorStatus
                    ),
                    connector_error_status=enumattr(
                        connector_attrs, 9, NobilConnector.ConnectorErrorStatus
                    ),
                    connector_status=enumattr(
                        connector_attrs, 8, NobilConnector.ConnectorStatus
                    ),
                    evse_uid=valattr(connector_attrs, 27),
                    fixed_cable=enumattr(connector_attrs, 25, bool),
                    evse_id=valattr(connector_attrs, 28),
                    connector_id=valattr(connector_attrs, 29),
                    charge_mode=enumattr(
                        connector_attrs, 20, NobilConnector.ChargeMode
                    ),
                    reservable=enumattr(connector_attrs, 18, bool),
                    manufacturer=valattr(connector_attrs, 23),
                )
                for connector_attrs in connectors.values()
            ],
        )
        yield charger
