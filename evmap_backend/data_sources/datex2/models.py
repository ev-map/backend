import uuid

from django.contrib.gis.db import models


class Datex2EnergyInfrastructureSite(models.Model):
    id_from_source = models.CharField(max_length=255)
    source = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    # TODO: operatingHours
    location = models.PointField()
    # TODO: address
    operatorName = models.CharField(max_length=255)
    operatorPhone = models.CharField(max_length=255)


class Datex2RefillPoint(models.Model):
    site = models.ForeignKey(Datex2EnergyInfrastructureSite, on_delete=models.CASCADE)
    id_from_source = models.CharField(max_length=255)
    externalIdentifier = models.CharField(max_length=255)  # EVSEID


class Datex2Connector(models.Model):
    class ConnectorTypes(models.TextChoices):
        CHADEMO = "chademo", "CHAdeMO"
        CEE3 = "cee3", "CEE3"
        CEE5 = "cee5", "CEE5"
        YAZAKI = "yazaki", "Yazaki"
        DOMESTIC = "domestic", "Domestic"
        DOMESTIC_A = "domesticA", "Domestic A"
        DOMESTIC_B = "domesticB", "Domestic B"
        DOMESTIC_C = "domesticC", "Domestic C"
        DOMESTIC_D = "domesticD", "Domestic D"
        DOMESTIC_E = "domesticE", "Domestic E"
        DOMESTIC_F = "domesticF", "Domestic F"
        DOMESTIC_G = "domesticG", "Domestic G"
        DOMESTIC_H = "domesticH", "Domestic H"
        DOMESTIC_I = "domesticI", "Domestic I"
        DOMESTIC_J = "domesticJ", "Domestic J"
        DOMESTIC_K = "domesticK", "Domestic K"
        DOMESTIC_L = "domesticL", "Domestic L"
        DOMESTIC_M = "domesticM", "Domestic M"
        DOMESTIC_N = "domesticN", "Domestic N"
        DOMESTIC_O = "domesticO", "Domestic O"
        IEC60309_2_SINGLE_16 = "iec60309x2single16", "CEE single-phase 16 A"
        IEC60309_2_THREE_16 = "iec60309x2three16", "CEE three-phase 16 A"
        IEC60309_2_THREE_32 = "iec60309x2three32", "CEE three-phase 32 A"
        IEC60309_2_THREE_64 = "iec60309x2three64", "CEE three-phase 63 A"
        TYPE_1 = "iec62196T1", "Type 1"
        CCS_TYPE_1 = "iec62196T1COMBO", "CCS Type 1"
        TYPE_2 = "iec62196T2", "Type 2"
        CCS_TYPE_2 = "iec62196T2COMBO", "CCS Type 2"
        TYPE_3A = "iec62196T3A", "Type 3A"
        TYPE_3C = "iec62196T3C", "Type 3C"
        PANTOGRAPH_BOTTOM_UP = "pantographBottomUp", "Pantograph bottom-up"
        PANTOGRAPH_TOP_DOWN = "pantographTopDown", "Pantograph top-down"
        TESLA_CONNECTOR_EUROPE = "teslaConnectorEurope", "Tesla Connector Europe"
        NACS = "teslaConnectorAmerica", "NACS"
        TESLA_R = "teslaR", "Tesla Roadster DC"
        TESLA_S = "teslaS", "Tesla S"  # ???
        OTHER = "other"

    class ChargingModes(models.TextChoices):
        MODE_1_AC_1P = "mode1AC1p", "Mode 1 - AC single-phase"
        MODE_1_AC_3P = "mode1AC3p", "Mode 1 - AC three-phase"
        MODE_2_AC_1P = "mode2AC1p", "Mode 2 - AC single-phase"
        MODE_2_AC_3P = "mode2AC3p", "Mode 2 - AC three-phase"
        MODE_3_AC_3P = "mode3AC3p", "Mode 3 - AC three-phase"
        MODE_4_DC = "mode4DC", "Mode 4 - DC"
        LEGACY_INDUCTIVE = "legacyInductive", "Legacy Inductive"
        CCS = "ccs", "CCS"
        OTHER = "other", "Other"
        UNKNOWN = "unknown", "Unknown"

    refill_point = models.ForeignKey(
        Datex2RefillPoint, on_delete=models.CASCADE, related_name="connectors"
    )
    connector_type = models.CharField(max_length=255, choices=ConnectorTypes)
    charging_mode = models.CharField(max_length=255, choices=ChargingModes)
    max_power = models.IntegerField()
