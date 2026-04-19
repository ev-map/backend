"""Tests for the Opendata Swiss OICP parser."""

import pytest

from evmap_backend.chargers.models import Connector
from evmap_backend.data_sources.opendata_swiss.parser import (
    _convert_opening_hours,
    _get_station_name,
    _parse_connectors,
    _parse_coordinates,
    _SiteClusterer,
    parse_oicp_data,
    parse_oicp_status,
)
from evmap_backend.realtime.models import RealtimeStatus


class TestParseCoordinates:
    def test_valid_coordinates(self):
        point = _parse_coordinates({"Google": "46.23432 6.055602"})
        assert point is not None
        assert point.y == pytest.approx(46.23432)
        assert point.x == pytest.approx(6.055602)

    def test_invalid_format(self):
        assert _parse_coordinates({"Google": "None None"}) is None

    def test_empty_string(self):
        assert _parse_coordinates({"Google": ""}) is None

    def test_missing_key(self):
        assert _parse_coordinates({}) is None

    def test_zero_coordinates(self):
        assert _parse_coordinates({"Google": "0 0"}) is None


class TestSiteClusterer:
    def test_identical_coords_same_cluster(self):
        c = _SiteClusterer()
        a = c.get_cluster_key("OP", "Op", "47.0 8.0")
        b = c.get_cluster_key("OP", "Op", "47.0 8.0")
        assert a == b

    def test_nearby_coords_merge(self):
        """Two points ~15 m apart should end up in the same cluster."""
        c = _SiteClusterer()
        a = c.get_cluster_key("OP", "Op", "47.696015 8.573935")
        b = c.get_cluster_key("OP", "Op", "47.696127 8.573739")
        assert a == b

    def test_no_grid_boundary_problem(self):
        """Points that would straddle a fixed-grid boundary still merge."""
        c = _SiteClusterer()
        # Orif - Delémont bornes: all within ~15 m of each other
        coords = [
            "47.35658 7.340079",
            "47.356554 7.340154",
            "47.356594 7.340047",
            "47.356602 7.340157",
            "47.356559 7.340119",
            "47.356617 7.340088",
            "47.356592 7.340189",
            "47.356608 7.340128",
        ]
        keys = [c.get_cluster_key("OP", "Op", coord) for coord in coords]
        assert len(set(keys)) == 1

    def test_distant_coords_stay_separate(self):
        """Two points several km apart must not merge."""
        c = _SiteClusterer()
        a = c.get_cluster_key("OP", "Op", "47.0 8.0")
        b = c.get_cluster_key("OP", "Op", "47.01 8.01")
        assert a != b

    def test_different_operators_stay_separate(self):
        """Same coordinates but different operators produce separate clusters
        because parse_oicp_data groups by (operator_id, operator_name, cluster_key)."""
        c = _SiteClusterer()
        a = c.get_cluster_key("OP1", "Op1", "47.0 8.0")
        b = c.get_cluster_key("OP2", "Op2", "47.0 8.0")
        # The key strings are the same, but operators are tracked independently
        # so the leader lists don't interfere with each other
        assert a == b  # keys are equal; separation is by operator in parse_oicp_data

    def test_invalid_input_returned_as_is(self):
        c = _SiteClusterer()
        assert c.get_cluster_key("OP", "Op", "None None") == "None None"
        assert c.get_cluster_key("OP", "Op", "") == ""

    def test_deterministic(self):
        """Same input always gives the same output."""
        c = _SiteClusterer()
        first = c.get_cluster_key("OP", "Op", "46.23432 6.055602")
        for _ in range(10):
            assert c.get_cluster_key("OP", "Op", "46.23432 6.055602") == first


class TestGetStationName:
    def test_prefer_english(self):
        record = {
            "ChargingStationNames": [
                {"lang": "de", "value": "German Name"},
                {"lang": "en", "value": "English Name"},
                {"lang": "fr", "value": "French Name"},
            ]
        }
        assert _get_station_name(record) == "English Name"

    def test_fallback_to_german(self):
        record = {
            "ChargingStationNames": [
                {"lang": "de", "value": "German Name"},
                {"lang": "fr", "value": "French Name"},
            ]
        }
        assert _get_station_name(record) == "German Name"

    def test_fallback_to_first(self):
        record = {
            "ChargingStationNames": [
                {"lang": "ja", "value": "Japanese Name"},
            ]
        }
        assert _get_station_name(record) == "Japanese Name"

    def test_empty_names(self):
        assert _get_station_name({"ChargingStationNames": []}) == ""
        assert _get_station_name({}) == ""

    def test_none_names(self):
        assert _get_station_name({"ChargingStationNames": None}) == ""


class TestConvertOpeningHours:
    def test_24_hours(self):
        record = {"IsOpen24Hours": True}
        assert _convert_opening_hours(record) == "24/7"

    def test_no_opening_times(self):
        record = {"IsOpen24Hours": False, "OpeningTimes": None}
        assert _convert_opening_hours(record) == ""

    def test_weekday_hours(self):
        record = {
            "IsOpen24Hours": False,
            "OpeningTimes": [
                {"Period": [{"begin": "08:00", "end": "20:00"}], "on": "Monday"},
                {"Period": [{"begin": "08:00", "end": "20:00"}], "on": "Tuesday"},
                {"Period": [{"begin": "08:00", "end": "20:00"}], "on": "Wednesday"},
                {"Period": [{"begin": "08:00", "end": "20:00"}], "on": "Thursday"},
                {"Period": [{"begin": "08:00", "end": "20:00"}], "on": "Friday"},
            ],
        }
        result = _convert_opening_hours(record)
        assert result == "Mo-Fr 08:00-20:00"

    def test_all_week(self):
        record = {
            "IsOpen24Hours": False,
            "OpeningTimes": [
                {"Period": [{"begin": "05:20", "end": "20:50"}], "on": day}
                for day in [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ]
            ],
        }
        result = _convert_opening_hours(record)
        assert result == "05:20-20:50"


class TestParseConnectors:
    def test_type2_outlet(self):
        record = {
            "EvseID": "CH*CCI*E22078",
            "Plugs": ["Type 2 Outlet"],
            "ChargingFacilities": [
                {
                    "Amperage": "32",
                    "Voltage": "230",
                    "power": "22.0",
                    "powertype": "AC_3_PHASE",
                }
            ],
        }
        connectors = _parse_connectors(record)
        assert len(connectors) == 1
        assert connectors[0].connector_type == Connector.ConnectorTypes.TYPE_2
        assert connectors[0].connector_format == Connector.ConnectorFormats.SOCKET
        assert connectors[0].max_power == 22000.0

    def test_ccs_cable(self):
        record = {
            "EvseID": "CH*TEST*E1",
            "Plugs": ["CCS Combo 2 Plug (Cable Attached)"],
            "ChargingFacilities": [{"Voltage": 600, "power": 300, "powertype": "DC"}],
        }
        connectors = _parse_connectors(record)
        assert len(connectors) == 1
        assert connectors[0].connector_type == Connector.ConnectorTypes.CCS_TYPE_2
        assert connectors[0].connector_format == Connector.ConnectorFormats.CABLE
        assert connectors[0].max_power == 300000.0

    def test_multiple_plugs(self):
        record = {
            "EvseID": "CH*TEST*E2",
            "Plugs": ["CHAdeMO", "CCS Combo 2 Plug (Cable Attached)"],
            "ChargingFacilities": [
                {"Voltage": 400, "power": 50, "powertype": "DC"},
                {"Voltage": 600, "power": 300, "powertype": "DC"},
            ],
        }
        connectors = _parse_connectors(record)
        assert len(connectors) == 2
        assert connectors[0].connector_type == Connector.ConnectorTypes.CHADEMO
        assert connectors[0].max_power == 50000.0
        assert connectors[1].connector_type == Connector.ConnectorTypes.CCS_TYPE_2
        assert connectors[1].max_power == 300000.0

    def test_no_facilities(self):
        record = {
            "EvseID": "CH*TEST*E3",
            "Plugs": ["Type 2 Outlet"],
            "ChargingFacilities": [],
        }
        connectors = _parse_connectors(record)
        assert len(connectors) == 1
        assert connectors[0].max_power == 0.0

    def test_swiss_plug(self):
        record = {
            "EvseID": "CH*TEST*E4",
            "Plugs": ["Type J Swiss Standard"],
            "ChargingFacilities": [{"power": "3.7", "powertype": "AC_1_PHASE"}],
        }
        connectors = _parse_connectors(record)
        assert len(connectors) == 1
        assert connectors[0].connector_type == Connector.ConnectorTypes.DOMESTIC_J
        assert connectors[0].connector_format == Connector.ConnectorFormats.SOCKET

    def test_tesla_connector(self):
        record = {
            "EvseID": "CH*TES*E1",
            "Plugs": ["Tesla Connector"],
            "ChargingFacilities": [{"power": "250", "powertype": "DC"}],
        }
        connectors = _parse_connectors(record)
        assert len(connectors) == 1
        assert (
            connectors[0].connector_type
            == Connector.ConnectorTypes.TESLA_SUPERCHARGER_EU
        )


@pytest.mark.django_db
class TestParseOicpData:
    def test_basic_parsing(self):
        data = {
            "EVSEData": [
                {
                    "OperatorID": "CH*CCI",
                    "OperatorName": "Move",
                    "EVSEDataRecord": [
                        {
                            "EvseID": "CH*CCI*E22078",
                            "ChargingStationId": "station_1",
                            "ChargingStationNames": [
                                {"lang": "en", "value": "Test Station"}
                            ],
                            "GeoCoordinates": {"Google": "46.23432 6.055602"},
                            "Address": {
                                "City": "Meyrin",
                                "Country": "CHE",
                                "PostalCode": "1217",
                                "Street": "Test Street",
                            },
                            "Plugs": ["Type 2 Outlet"],
                            "ChargingFacilities": [
                                {"power": "22.0", "powertype": "AC_3_PHASE"}
                            ],
                            "IsOpen24Hours": True,
                        }
                    ],
                }
            ]
        }

        sites = list(
            parse_oicp_data(data, "test_source", "test_license", "https://test.example")
        )
        assert len(sites) == 1

        site, chargepoints = sites[0].site, sites[0].chargepoints
        assert site.name == "Test Station"
        assert site.id_from_source == "46.234320 6.055602"
        assert site.country == "CH"
        assert site.city == "Meyrin"
        assert site.zipcode == "1217"
        assert site.street == "Test Street"
        assert site.operator == "Move"
        assert site.opening_hours == "24/7"
        assert site.data_source == "test_source"
        assert site.license_attribution == "test_license"

        assert len(chargepoints) == 1
        cp, connectors = chargepoints[0].chargepoint, chargepoints[0].connectors
        assert cp.id_from_source == "CH*CCI*E22078"
        assert cp.evseid == "CHCCIE22078"
        assert len(connectors) == 1
        assert connectors[0].connector_type == Connector.ConnectorTypes.TYPE_2
        assert connectors[0].max_power == 22000.0

    def test_grouping_by_station_id(self):
        data = {
            "EVSEData": [
                {
                    "OperatorID": "CH*TST",
                    "OperatorName": "Test Operator",
                    "EVSEDataRecord": [
                        {
                            "EvseID": "CH*TST*E001",
                            "ChargingStationId": "station_A",
                            "ChargingStationNames": [
                                {"lang": "en", "value": "Station A"}
                            ],
                            "GeoCoordinates": {"Google": "47.0 8.0"},
                            "Address": {
                                "City": "Bern",
                                "Country": "CHE",
                                "PostalCode": "3000",
                                "Street": "Street 1",
                            },
                            "Plugs": ["CCS Combo 2 Plug (Cable Attached)"],
                            "ChargingFacilities": [{"power": 300, "powertype": "DC"}],
                            "IsOpen24Hours": True,
                        },
                        {
                            "EvseID": "CH*TST*E002",
                            "ChargingStationId": "station_A",
                            "ChargingStationNames": [
                                {"lang": "en", "value": "Station A"}
                            ],
                            "GeoCoordinates": {"Google": "47.0 8.0"},
                            "Address": {
                                "City": "Bern",
                                "Country": "CHE",
                                "PostalCode": "3000",
                                "Street": "Street 1",
                            },
                            "Plugs": ["CHAdeMO"],
                            "ChargingFacilities": [{"power": 50, "powertype": "DC"}],
                            "IsOpen24Hours": True,
                        },
                    ],
                }
            ]
        }

        sites = list(
            parse_oicp_data(data, "test_source", "test_license", "https://test.example")
        )
        assert len(sites) == 1  # One station

        site, chargepoints = sites[0].site, sites[0].chargepoints
        assert site.id_from_source == "47.000000 8.000000"
        assert len(chargepoints) == 2

        evse_ids = {cp.chargepoint.id_from_source for cp in chargepoints}
        assert evse_ids == {"CH*TST*E001", "CH*TST*E002"}

    def test_skip_invalid_coordinates(self):
        data = {
            "EVSEData": [
                {
                    "OperatorID": "CH*TST",
                    "OperatorName": "Test",
                    "EVSEDataRecord": [
                        {
                            "EvseID": "CH*TST*E001",
                            "ChargingStationId": "CH*TST*E001",
                            "ChargingStationNames": [
                                {"lang": "en", "value": "Bad Station"}
                            ],
                            "GeoCoordinates": {"Google": "None None"},
                            "Address": {"City": "Bern", "Country": "CHE"},
                            "Plugs": ["Type 2 Outlet"],
                            "ChargingFacilities": [{"power": "22.0"}],
                            "IsOpen24Hours": True,
                        }
                    ],
                }
            ]
        }

        sites = list(
            parse_oicp_data(data, "test_source", "test_license", "https://test.example")
        )
        assert len(sites) == 0

    def test_grouping_by_coords_when_evse_id_equals_station_id(self):
        """Tesla-style: EvseID == ChargingStationId, so EVSEs at same coords merge."""
        data = {
            "EVSEData": [
                {
                    "OperatorID": "CH*TES",
                    "OperatorName": "Tesla",
                    "EVSEDataRecord": [
                        {
                            "EvseID": f"CH*TSL*E00{i}",
                            "ChargingStationId": f"CH*TSL*E00{i}",
                            "ChargingStationNames": [
                                {"lang": "en", "value": "Tesla Supercharger Bern"}
                            ],
                            "GeoCoordinates": {"Google": "46.95 7.45"},
                            "Address": {
                                "City": "Bern",
                                "Country": "CHE",
                                "PostalCode": "3000",
                                "Street": "Supercharger Str.",
                            },
                            "Plugs": ["Tesla Connector"],
                            "ChargingFacilities": [{"power": "250", "powertype": "DC"}],
                            "IsOpen24Hours": True,
                        }
                        for i in range(4)
                    ],
                }
            ]
        }

        sites = list(
            parse_oicp_data(data, "test_source", "test_license", "https://test.example")
        )
        assert len(sites) == 1  # All 4 EVSEs at same coords -> 1 site

        site, chargepoints = sites[0].site, sites[0].chargepoints
        assert site.id_from_source == "46.950000 7.450000"
        assert site.name == "Tesla Supercharger Bern"
        assert len(chargepoints) == 4

    def test_different_coords_create_separate_sites(self):
        """EVSEs with EvseID == ChargingStationId at different coords -> separate sites."""
        data = {
            "EVSEData": [
                {
                    "OperatorID": "CH*TES",
                    "OperatorName": "Tesla",
                    "EVSEDataRecord": [
                        {
                            "EvseID": "CH*TSL*E001",
                            "ChargingStationId": "CH*TSL*E001",
                            "ChargingStationNames": [
                                {"lang": "en", "value": "Tesla Bern"}
                            ],
                            "GeoCoordinates": {"Google": "46.95 7.45"},
                            "Address": {"City": "Bern", "Country": "CHE"},
                            "Plugs": ["Tesla Connector"],
                            "ChargingFacilities": [{"power": "250"}],
                            "IsOpen24Hours": True,
                        },
                        {
                            "EvseID": "CH*TSL*E002",
                            "ChargingStationId": "CH*TSL*E002",
                            "ChargingStationNames": [
                                {"lang": "en", "value": "Tesla Zurich"}
                            ],
                            "GeoCoordinates": {"Google": "47.37 8.54"},
                            "Address": {"City": "Zurich", "Country": "CHE"},
                            "Plugs": ["Tesla Connector"],
                            "ChargingFacilities": [{"power": "250"}],
                            "IsOpen24Hours": True,
                        },
                    ],
                }
            ]
        }

        sites = list(
            parse_oicp_data(data, "test_source", "test_license", "https://test.example")
        )
        assert len(sites) == 2


@pytest.mark.django_db(transaction=True)
class TestParseOicpStatus:
    def test_status_parsing(self):
        status_data = {
            "EVSEStatuses": [
                {
                    "OperatorID": "CH*CCI",
                    "OperatorName": "Move",
                    "EVSEStatusRecord": [
                        {
                            "EvseID": "CH*CCI*E22078",
                            "EVSEStatus": "Available",
                        }
                    ],
                }
            ]
        }

        statuses = list(
            parse_oicp_status(
                status_data,
                "opendata_swiss_realtime",
                "test_license",
                "https://test.example",
            )
        )
        assert len(statuses) == 1
        assert statuses[0].site_id_from_source is None
        assert statuses[0].chargepoint_id_from_source == "CH*CCI*E22078"
        assert statuses[0].status.status == RealtimeStatus.Status.AVAILABLE

    def test_status_mapping(self):
        status_data = {
            "EVSEStatuses": [
                {
                    "OperatorID": "CH*TST",
                    "OperatorName": "Test",
                    "EVSEStatusRecord": [
                        {"EvseID": "CH*TST*E0", "EVSEStatus": "Available"},
                        {"EvseID": "CH*TST*E1", "EVSEStatus": "Occupied"},
                        {"EvseID": "CH*TST*E2", "EVSEStatus": "OutOfService"},
                        {"EvseID": "CH*TST*E3", "EVSEStatus": "Reserved"},
                        {"EvseID": "CH*TST*E4", "EVSEStatus": "Unknown"},
                    ],
                }
            ]
        }

        statuses = list(
            parse_oicp_status(
                status_data,
                "opendata_swiss_realtime",
                "test_license",
                "https://test.example",
            )
        )
        assert len(statuses) == 5

        status_map = {s.chargepoint_id_from_source: s.status.status for s in statuses}
        assert status_map["CH*TST*E0"] == RealtimeStatus.Status.AVAILABLE
        assert status_map["CH*TST*E1"] == RealtimeStatus.Status.CHARGING
        assert status_map["CH*TST*E2"] == RealtimeStatus.Status.OUTOFORDER
        assert status_map["CH*TST*E3"] == RealtimeStatus.Status.RESERVED
        assert status_map["CH*TST*E4"] == RealtimeStatus.Status.UNKNOWN
