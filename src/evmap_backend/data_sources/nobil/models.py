from django.contrib.gis.db import models
from solo.models import SingletonModel


class NobilChargerStation(models.Model):
    class LocationType(models.IntegerChoices):
        STREET = 1, "Street"
        CAR_PARK = 2, "Car park"
        AIRPORT = 3, "Airport"
        SHOPPING_CENTER = 4, "Shopping center"
        TRANSPORT_HUB = 5, "Transport hub"
        HOTELS_RESTAURANTS = 6, "Hotels & Restaurants"
        GAS_STATION = 7, "Gas station"

    class Availability(models.IntegerChoices):
        PUBLIC = 1, "Public"
        VISITORS = 2, "Visitors"
        EMPLOYEES = 3, "Employees"
        BY_APPOINTMENT = 4, "By appointment"
        RESIDENTS = 5, "Residents"

    class PublicFunding(models.IntegerChoices):
        OSLO_KOMMUNE = 1, "Oslo kommune"
        TRANSNOVA = 2, "Transnova"
        OTHER = 3, "Other"
        NONE = 4, "None"
        KLIMASTEGET = 5, "Klimasteget"
        TRAFIKKVERKET = 6, "Trafikkverket"

    # csmd data
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    location = models.PointField()
    ocpi_id = models.CharField(max_length=255, blank=True)
    street = models.CharField(max_length=255)
    house_number = models.CharField(max_length=10)
    zip_code = models.CharField(max_length=10)
    city = models.CharField(max_length=255)
    municipality_id = models.CharField(max_length=255)
    municipality = models.CharField(max_length=255)
    county_id = models.CharField(max_length=255)
    county = models.CharField(max_length=255)
    description_of_location = models.TextField(blank=True)
    owned_by = models.CharField(max_length=255, blank=True)
    operator = models.CharField(max_length=255, blank=True)
    num_chargepoints = models.IntegerField()
    image = models.CharField(max_length=255, blank=True)
    available_chargepoints = models.IntegerField()
    user_comment = models.TextField(blank=True)
    contact_info = models.TextField(blank=True)
    created = models.DateTimeField()
    updated = models.DateTimeField()
    station_status = models.IntegerField()
    land_code = models.CharField(max_length=10)
    international_id = models.CharField(max_length=255)
    # station attrs
    location_type = models.IntegerField(choices=LocationType)
    availability = models.IntegerField(choices=Availability)
    open_24h = models.BooleanField()
    parking_fee = models.BooleanField()
    time_limit = models.BooleanField()
    real_time_information = models.BooleanField()
    public_funding = models.IntegerField(choices=PublicFunding)


class NobilConnector(models.Model):
    class VehicleType(models.IntegerChoices):
        E_ALL = 15, "All rechargeable vehicles"
        E_CARS_VANS = 1, "Rechargeable cars and vans"
        E_VANS = 6, "Rechargeable vans"
        E_TRUCKS = (
            10,
            "Rechargeable medium or heavy trucks",
        )
        E_BUSES = (
            13,
            "Rechargeable buses",
        )
        E_BUSES_TRUCKS = (
            14,
            "Rechargeable buses and trucks",
        )
        E_BOATS = (
            20,
            "Rechargeable boats",
        )
        E_CARS_VANS_BOATS = (
            22,
            "Rechargeable cars, vans and boats",
        )

        H_ALL = (
            7,
            "All hydrogen vehicles",
        )
        H_CARS = (
            8,
            "Hydrogen cars",
        )
        H_TRUCKS = (
            9,
            "Hydrogen trucks",
        )

        E_H_CARS_VANS = (
            12,
            "Hydrogen and rechargeable cars and vans",
        )

        BIOGAS = 16, "Biogas vehicles"

        ALL = (
            11,
            "All vehicles",
        )

    class Accessibility(models.IntegerChoices):
        OPEN = 1, "Open"
        STANDARD_KEY = 2, "Standard key"
        OTHER = 3, "Other"
        RFID = 4, "RFID"
        PAYMENT = 5, "Payment"
        CELLULAR_PHONE = 6, "Cellular Phone"

    class EnergyCarrier(models.IntegerChoices):
        ELECTRICITY = 1, "Electricity"
        HYDROGEN = 2, "Hydrogen"
        BIOGAS = 3, "Biogas"

    class Connector(models.IntegerChoices):
        TYPE_1 = 31, "Type 1"
        TYPE_2 = 32, "Type 2"
        CHADEMO = 30, "CHAdeMO"
        CCS = 39, "CCS/Combo"
        TESLA = 40, "Tesla Connector Model"
        TYPE_2_SCHUKO = 50, "Type 2 + Schuko"
        TYPE_1_TYPE_2 = 60, "Type 1/Type 2"
        HYDROGEN = 70, "Hydrogen"
        BIOGAS = 82, "Biogas"
        UNSPECIFIED = 0, "Unspecified"

    class ChargingCapacity(models.IntegerChoices):
        AC_3_6 = 7, "3,6 kW - 230V 1-phase max 16A"
        AC_7_4 = 8, "7,4 kW - 230V 1-phase max 32A"
        AC_11 = 10, "11 kW - 400V 3-phase max 16A"
        DC_20 = 19, "20 kW DC - 500VDC max 50A"
        AC_22 = 11, "11 kW - 400V 3-phase max 32A"
        DC_30 = 37, "30 kW DC"
        AC_43 = 12, "43 kW - 400V 3-phase max 63A"
        DC_62_5 = 38, "62.5 kW DC"
        DC_50 = 13, "50 kW DC - 500VDC max 100A"
        DC_75 = 29, "75 kW DC"
        DC_100 = 23, "100 kW DC - 500VDC max 200A"
        DC_135 = 22, "135 kW DC - 480VDC max 270A"
        DC_150 = 24, "150 kW DC"
        DC_175 = 41, "175 kW DC"
        DC_180 = 42, "180 kW DC"
        DC_200 = 32, "200 kW DC"
        DC_225 = 30, "225 kW DC"
        DC_250 = 31, "250 kW DC"
        DC_300 = 33, "300 kW DC"
        DC_350 = 25, "350 kW DC"
        DC_400 = 36, "400 kW DC"
        DC_500 = 39, "500 kW DC"
        UNSPECIFIED = 0, "Unspecified"
        AC_11_ALT = 16, "230V 3-phase max 16A"
        AC_22_ALT = 17, "230V 3-phase max 32A"
        AC_43_ALT = 18, "230V 3-phase max 63A"
        H_350 = 26, "350 bar"
        H_700 = 27, "700 bar"
        CBG = 34, "CBG"
        LBG = 35, "LBG"

    class PaymentMethod(models.IntegerChoices):
        CELLPHONE = 1, "Cellular Phone"
        BANK_CARD = 2, "Bank Card"
        MISCELLANEOUS = 3, "Miscellaneous"
        CELLPHONE_CHARGING_CARD = 20, "Cellular Phone and Charging Card"
        BANK_CARD_CHARGING_CARD = (
            21,
            "Bank Card and Charging Card",
        )
        BANK_CARD_CHARGING_CARD_CELLPHONE = (
            25,
            "Bank Card, Charging Card and Cellular Phone",
        )

    class ConnectorSensorStatus(models.IntegerChoices):
        VACANT = 0, "Vacant"
        BUSY = 1, "Busy (charging)"

    class ConnectorErrorStatus(models.IntegerChoices):
        IN_SERVICE = 0, "In Service"
        OUT_OF_SERVICE = 1, "Error - Out of Service"

    class ConnectorStatus(models.IntegerChoices):
        VACANT = 0, "Vacant"
        BUSY = 1, "Busy (charging)"
        RESERVED = 2, "Reserved"

    class ChargeMode(models.IntegerChoices):
        MODE_1 = 1, "Mode 1"
        MODE_2 = 2, "Mode 2"
        MODE_3 = 3, "Mode 3"
        MODE_4 = 4, "Mode 4"

    charging_station = models.ForeignKey(NobilChargerStation, on_delete=models.CASCADE)
    vehicle_type = models.IntegerField(choices=VehicleType, blank=True, null=True)
    accessibility = models.IntegerField(choices=Accessibility, blank=True, null=True)
    energy_carrier = models.IntegerField(choices=EnergyCarrier, blank=True, null=True)
    connector = models.IntegerField(choices=Connector, blank=True, null=True)
    charging_capacity = models.IntegerField(
        choices=ChargingCapacity, blank=True, null=True
    )
    voltage = models.IntegerField(blank=True, null=True)
    amperage = models.IntegerField(blank=True, null=True)
    payment_method = models.IntegerField(choices=PaymentMethod, blank=True, null=True)
    timestamp = models.DateTimeField(blank=True, null=True)
    power_consumption = models.IntegerField(blank=True, null=True)
    connector_sensor_status = models.IntegerField(
        choices=ConnectorSensorStatus, blank=True, null=True
    )
    connector_error_status = models.IntegerField(
        choices=ConnectorErrorStatus, blank=True, null=True
    )
    connector_status = models.IntegerField(
        choices=ConnectorStatus, blank=True, null=True
    )
    # meter_value =
    # last_usage =
    evse_uid = models.CharField(max_length=255, blank=True)
    fixed_cable = models.BooleanField(blank=True, null=True)
    evse_id = models.CharField(max_length=255, blank=True)
    connector_id = models.CharField(max_length=255, blank=True)
    charge_mode = models.IntegerField(choices=ChargeMode, blank=True, null=True)
    # party_id =
    reservable = models.BooleanField(blank=True, null=True)
    manufacturer = models.CharField(max_length=255, blank=True)


class NobilUpdateState(SingletonModel):
    last_update = models.DateTimeField(null=True)


class NobilRealtimeData(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        """Evse is able to start a new charging session"""
        BLOCKED = "BLOCKED", "Blocked"
        """Evse is not accessible because of a physical barrier, i.e. a car"""
        CHARGING = "CHARGING", "Charging"
        """EVSE is in use"""
        INOPERATIVE = "INOPERATIVE", "Inoperative"
        """EVSE is not yet active or it is no longer available (deleted)"""
        OUTOFORDER = "OUTOFORDER", "Out of order"
        """EVSE is currently out of order"""
        PLANNED = "PLANNED", "Planned"
        """EVSE is planned, will be operating soon"""
        REMOVED = "REMOVED", "Removed"
        """EVSE is discontinued/removed."""
        RESERVED = "RESERVED", "Reserved"
        """EVSE is reserved for a particular EV driver and is unavailable for other drivers"""
        UNKNOWN = "UNKNOWN", "Unknown"
        """No status information available. (Also used when offline)"""

    nobil_id = models.CharField(max_length=20)
    evse_uid = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=Status)
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        get_latest_by = "timestamp"
        indexes = [
            models.Index(fields=["nobil_id", "evse_uid", "timestamp"]),
        ]
