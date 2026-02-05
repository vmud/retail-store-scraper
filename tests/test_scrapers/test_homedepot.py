"""Unit tests for Home Depot scraper."""
# pylint: disable=no-member  # Mock objects have dynamic attributes

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call

from config import homedepot_config
from src.scrapers.homedepot import (
    HomeDepotStore,
    _post_graphql,
    _format_day_hours,
    _format_hours_json,
    discover_stores,
    extract_store_details,
    run,
)
from src.shared.request_counter import RequestCounter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_store():
    """Create a sample HomeDepotStore for testing."""
    return HomeDepotStore(
        store_id="121",
        name="Cumberland",
        street_address="2450 Cumberland Pkwy",
        city="Atlanta",
        state="GA",
        zip="30339",
        county="Cobb",
        country="US",
        latitude=33.862126,
        longitude=-84.476161,
        timezone="EST5EDT",
        phone="(770)432-9930",
        pro_desk_phone="(770)801-6415",
        tool_rental_phone="(770)801-6400",
        services_phone="(844) 476-2140",
        url="https://www.homedepot.com/l/Cumberland/GA/Atlanta/30339/121",
        store_type="retail",
        scraped_at="2026-02-05T12:00:00",
        hours_mon="6:00-22:00",
        hours_tue="6:00-22:00",
        hours_wed="6:00-22:00",
        hours_thu="6:00-22:00",
        hours_fri="6:00-22:00",
        hours_sat="6:00-22:00",
        hours_sun="8:00-20:00",
        service_load_n_go=True,
        service_propane=True,
        service_tool_rental=True,
        service_penske=True,
        service_key_cutting=True,
        service_wifi=True,
        service_appliance_showroom=False,
        service_flooring_showroom=True,
        service_large_equipment=True,
        service_kitchen_showroom=True,
        service_hd_moving=False,
        flag_bopis=True,
        flag_bodfs=True,
        flag_curbside=True,
        pro_desk_hours='{"monday": "6:00-22:00"}',
        tool_rental_hours='{"monday": "6:00-22:00"}',
        curbside_hours='{"monday": "09:00-18:00"}',
    )


@pytest.fixture
def sample_state_response():
    """Sample storeDirectoryByState GraphQL response."""
    return {
        "data": {
            "storeDirectoryByState": {
                "stateName": "Georgia",
                "storesInfo": [
                    {
                        "storeName": "Cumberland",
                        "url": "https://www.homedepot.com/l/Cumberland/GA/Atlanta/30339/121",
                        "phone": "(770)432-9930",
                        "rentalsLink": "https://www.homedepot.com/l/Cumberland/GA/Atlanta/30339/121/rentals",
                        "servicesLink": "https://www.homedepot.com/l/Cumberland/GA/Atlanta/30339/121/services",
                        "address": {
                            "street": "2450 Cumberland Pkwy",
                            "city": "Atlanta",
                            "state": "GA",
                            "postalCode": "30339",
                            "county": "Cobb"
                        }
                    },
                    {
                        "storeName": "Kennesaw",
                        "url": "https://www.homedepot.com/l/Kennesaw/GA/Kennesaw/30144/576",
                        "phone": "(770)514-1400",
                        "rentalsLink": None,
                        "servicesLink": None,
                        "address": {
                            "street": "455 Barrett Pkwy NW",
                            "city": "Kennesaw",
                            "state": "GA",
                            "postalCode": "30144",
                            "county": "Cobb"
                        }
                    }
                ]
            }
        }
    }


@pytest.fixture
def sample_store_search_response():
    """Sample storeSearch GraphQL response."""
    return {
        "data": {
            "storeSearch": {
                "stores": [
                    {
                        "storeId": "0121",
                        "name": "Cumberland",
                        "address": {
                            "street": "2450 Cumberland Pkwy",
                            "city": "Atlanta",
                            "state": "GA",
                            "postalCode": "30339",
                            "country": "US"
                        },
                        "coordinates": {
                            "lat": 33.862126,
                            "lng": -84.476161
                        },
                        "services": {
                            "loadNGo": True,
                            "propane": True,
                            "toolRental": True,
                            "penske": True,
                            "keyCutting": True,
                            "wiFi": True,
                            "applianceShowroom": False,
                            "expandedFlooringShowroom": True,
                            "largeEquipment": True,
                            "kitchenShowroom": True,
                            "hdMoving": False
                        },
                        "storeHours": {
                            "monday": {"open": "6:00", "close": "22:00"},
                            "tuesday": {"open": "6:00", "close": "22:00"},
                            "wednesday": {"open": "6:00", "close": "22:00"},
                            "thursday": {"open": "6:00", "close": "22:00"},
                            "friday": {"open": "6:00", "close": "22:00"},
                            "saturday": {"open": "6:00", "close": "22:00"},
                            "sunday": {"open": "8:00", "close": "20:00"}
                        },
                        "storeDetailsPageLink": "/l/Cumberland/GA/Atlanta/30339/121",
                        "storeType": "retail",
                        "proDeskPhone": "(770)801-6415",
                        "phone": "(770)432-9930",
                        "toolRentalPhone": "(770)801-6400",
                        "storeServicesPhone": "(844) 476-2140",
                        "flags": {
                            "bopisFlag": True,
                            "bodfsFlag": True,
                            "curbsidePickupFlag": True
                        },
                        "storeTimeZone": "EST5EDT",
                        "proDeskHours": {
                            "monday": {"open": "6:00", "close": "22:00"},
                            "tuesday": {"open": "6:00", "close": "22:00"},
                            "wednesday": {"open": "6:00", "close": "22:00"},
                            "thursday": {"open": "6:00", "close": "22:00"},
                            "friday": {"open": "6:00", "close": "22:00"},
                            "saturday": {"open": "6:00", "close": "22:00"},
                            "sunday": {"open": "8:00", "close": "20:00"}
                        },
                        "toolRentalHours": {
                            "monday": {"open": "6:00", "close": "22:00"},
                            "tuesday": {"open": "6:00", "close": "22:00"},
                            "wednesday": {"open": "6:00", "close": "22:00"},
                            "thursday": {"open": "6:00", "close": "22:00"},
                            "friday": {"open": "6:00", "close": "22:00"},
                            "saturday": {"open": "6:00", "close": "22:00"},
                            "sunday": {"open": "8:00", "close": "20:00"}
                        },
                        "curbsidePickupHours": {
                            "monday": {"open": "09:00", "close": "18:00"},
                            "tuesday": {"open": "09:00", "close": "18:00"},
                            "wednesday": {"open": "09:00", "close": "18:00"},
                            "thursday": {"open": "09:00", "close": "18:00"},
                            "friday": {"open": "09:00", "close": "18:00"},
                            "saturday": {"open": "09:00", "close": "18:00"},
                            "sunday": {"open": "09:00", "close": "18:00"}
                        }
                    }
                ],
                "suggestedAddresses": []
            }
        }
    }


@pytest.fixture
def mock_session():
    """Create a mock requests session."""
    return Mock()


@pytest.fixture
def yaml_config():
    """Minimal YAML config for testing."""
    return {
        "delays": {
            "direct": {"min_delay": 0.5, "max_delay": 1.0},
            "proxied": {"min_delay": 0.2, "max_delay": 0.4},
        },
        "proxy": {"mode": "direct"},
        "parallel_workers": 5,
        "checkpoint_interval": 100,
    }


# ---------------------------------------------------------------------------
# TestHomeDepotStore
# ---------------------------------------------------------------------------

class TestHomeDepotStore:
    """Tests for HomeDepotStore dataclass."""

    def test_to_dict_full_data(self, sample_store):
        """Test dict conversion with all fields populated."""
        result = sample_store.to_dict()

        assert result["store_id"] == "121"
        assert result["name"] == "Cumberland"
        assert result["street_address"] == "2450 Cumberland Pkwy"
        assert result["city"] == "Atlanta"
        assert result["state"] == "GA"
        assert result["zip"] == "30339"
        assert result["county"] == "Cobb"
        assert result["country"] == "US"
        assert result["store_type"] == "retail"
        assert result["phone"] == "(770)432-9930"
        assert result["pro_desk_phone"] == "(770)801-6415"
        assert result["url"] == "https://www.homedepot.com/l/Cumberland/GA/Atlanta/30339/121"
        assert result["timezone"] == "EST5EDT"

    def test_to_dict_coordinate_conversion(self, sample_store):
        """Test that coordinates are converted to strings for CSV compat."""
        result = sample_store.to_dict()

        assert result["latitude"] == "33.862126"
        assert result["longitude"] == "-84.476161"
        assert isinstance(result["latitude"], str)
        assert isinstance(result["longitude"], str)

    def test_to_dict_none_coordinates(self):
        """Test that None coordinates become empty strings."""
        store = HomeDepotStore(
            store_id="999", name="Test", street_address="123 St",
            city="Test", state="TX", zip="75001", county="", country="US",
            latitude=None, longitude=None, timezone="", phone="",
            pro_desk_phone="", tool_rental_phone="", services_phone="",
            url="", store_type="", scraped_at="",
            hours_mon="", hours_tue="", hours_wed="", hours_thu="",
            hours_fri="", hours_sat="", hours_sun="",
            service_load_n_go=False, service_propane=False,
            service_tool_rental=False, service_penske=False,
            service_key_cutting=False, service_wifi=False,
            service_appliance_showroom=False, service_flooring_showroom=False,
            service_large_equipment=False, service_kitchen_showroom=False,
            service_hd_moving=False,
            flag_bopis=False, flag_bodfs=False, flag_curbside=False,
            pro_desk_hours="", tool_rental_hours="", curbside_hours="",
        )
        result = store.to_dict()

        assert result["latitude"] == ""
        assert result["longitude"] == ""

    def test_to_dict_service_flags(self, sample_store):
        """Test that boolean service/flag fields are preserved."""
        result = sample_store.to_dict()

        assert result["service_load_n_go"] is True
        assert result["service_hd_moving"] is False
        assert result["flag_bopis"] is True
        assert result["flag_curbside"] is True

    def test_to_dict_hours_fields(self, sample_store):
        """Test that hours strings are preserved."""
        result = sample_store.to_dict()

        assert result["hours_mon"] == "6:00-22:00"
        assert result["hours_sun"] == "8:00-20:00"

    def test_to_dict_json_hours_fields(self, sample_store):
        """Test that specialty hours JSON strings are preserved."""
        result = sample_store.to_dict()

        assert result["pro_desk_hours"] == '{"monday": "6:00-22:00"}'
        assert isinstance(result["curbside_hours"], str)


# ---------------------------------------------------------------------------
# TestFormatHours
# ---------------------------------------------------------------------------

class TestFormatHours:
    """Tests for _format_day_hours and _format_hours_json."""

    def test_format_day_hours_normal(self):
        """Test formatting normal open/close hours."""
        day_data = {"open": "6:00", "close": "22:00"}
        assert _format_day_hours(day_data) == "6:00-22:00"

    def test_format_day_hours_none(self):
        """Test formatting when day_data is None."""
        assert _format_day_hours(None) == ""

    def test_format_day_hours_empty_dict(self):
        """Test formatting when day_data is empty dict."""
        assert _format_day_hours({}) == ""

    def test_format_day_hours_missing_close(self):
        """Test formatting when close is missing."""
        day_data = {"open": "6:00"}
        assert _format_day_hours(day_data) == ""

    def test_format_day_hours_missing_open(self):
        """Test formatting when open is missing."""
        day_data = {"close": "22:00"}
        assert _format_day_hours(day_data) == ""

    def test_format_hours_json_full(self):
        """Test JSON serialization of specialty hours."""
        hours = {
            "monday": {"open": "6:00", "close": "22:00"},
            "tuesday": {"open": "6:00", "close": "22:00"},
        }
        result = _format_hours_json(hours)
        parsed = json.loads(result)

        assert parsed["monday"] == "6:00-22:00"
        assert parsed["tuesday"] == "6:00-22:00"

    def test_format_hours_json_none(self):
        """Test JSON serialization when hours is None."""
        assert _format_hours_json(None) == ""

    def test_format_hours_json_empty(self):
        """Test JSON serialization when hours is empty dict."""
        assert _format_hours_json({}) == ""


# ---------------------------------------------------------------------------
# TestPostGraphql
# ---------------------------------------------------------------------------

class TestPostGraphql:
    """Tests for _post_graphql function."""

    @patch('src.scrapers.homedepot.random_delay')
    def test_success(self, mock_delay, mock_session):
        """Test successful GraphQL POST."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"storeDirectory": {"storeDirectory": []}}
        }
        mock_session.post.return_value = mock_response

        result = _post_graphql(
            mock_session,
            operation_name="storeDirectory",
            query="query storeDirectory { storeDirectory { storeDirectory { stateName } } }",
            variables={},
        )

        assert result == {"data": {"storeDirectory": {"storeDirectory": []}}}
        mock_session.post.assert_called_once()

    @patch('src.scrapers.homedepot.time.sleep')
    @patch('src.scrapers.homedepot.random_delay')
    def test_retry_on_429(self, mock_delay, mock_sleep, mock_session):
        """Test retry on 429 rate limit."""
        mock_429 = Mock()
        mock_429.status_code = 429

        mock_200 = Mock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"data": {}}

        mock_session.post.side_effect = [mock_429, mock_200]

        result = _post_graphql(
            mock_session,
            operation_name="test",
            query="query { test }",
            variables={},
            max_retries=3,
        )

        assert result == {"data": {}}
        assert mock_session.post.call_count == 2
        mock_sleep.assert_called_once()

    @patch('src.scrapers.homedepot.time.sleep')
    @patch('src.scrapers.homedepot.random_delay')
    def test_retry_on_500(self, mock_delay, mock_sleep, mock_session):
        """Test retry on server error."""
        mock_500 = Mock()
        mock_500.status_code = 500

        mock_200 = Mock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"data": {}}

        mock_session.post.side_effect = [mock_500, mock_200]

        result = _post_graphql(
            mock_session,
            operation_name="test",
            query="query { test }",
            variables={},
            max_retries=3,
        )

        assert result == {"data": {}}
        assert mock_session.post.call_count == 2
        mock_sleep.assert_called_once()

    @patch('src.scrapers.homedepot.time.sleep')
    @patch('src.scrapers.homedepot.random_delay')
    def test_max_retries_exhausted(self, mock_delay, mock_sleep, mock_session):
        """Test that None is returned after max retries."""
        mock_500 = Mock()
        mock_500.status_code = 500

        mock_session.post.return_value = mock_500

        result = _post_graphql(
            mock_session,
            operation_name="test",
            query="query { test }",
            variables={},
            max_retries=2,
        )

        assert result is None
        assert mock_session.post.call_count == 2
        assert mock_sleep.call_count == 2

    @patch('src.scrapers.homedepot.random_delay')
    def test_fail_fast_on_4xx(self, mock_delay, mock_session):
        """Test immediate failure on non-retryable client errors."""
        mock_400 = Mock()
        mock_400.status_code = 400

        mock_session.post.return_value = mock_400

        result = _post_graphql(
            mock_session,
            operation_name="test",
            query="query { test }",
            variables={},
            max_retries=3,
        )

        assert result is None
        assert mock_session.post.call_count == 1

    @patch('src.scrapers.homedepot.random_delay')
    def test_graphql_errors_returns_none(self, mock_delay, mock_session):
        """Test that GraphQL-level errors in the response return None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Variable not found"}],
            "data": None
        }
        mock_session.post.return_value = mock_response

        result = _post_graphql(
            mock_session,
            operation_name="test",
            query="query { test }",
            variables={},
        )

        assert result is None

    @patch('src.scrapers.homedepot.time.sleep')
    @patch('src.scrapers.homedepot.random_delay')
    def test_retry_on_403(self, mock_delay, mock_sleep, mock_session):
        """Test retry on 403 blocked response."""
        mock_403 = Mock()
        mock_403.status_code = 403

        mock_200 = Mock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"data": {}}

        mock_session.post.side_effect = [mock_403, mock_200]

        result = _post_graphql(
            mock_session,
            operation_name="test",
            query="query { test }",
            variables={},
            max_retries=3,
        )

        assert result == {"data": {}}
        assert mock_session.post.call_count == 2
        mock_sleep.assert_called_once()

    @patch('src.scrapers.homedepot.time.sleep')
    @patch('src.scrapers.homedepot.random_delay')
    def test_network_exception_retry(self, mock_delay, mock_sleep, mock_session):
        """Test retry on network exception with credential redaction."""
        import requests as req

        mock_200 = Mock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"data": {"result": True}}

        mock_session.post.side_effect = [
            req.exceptions.ConnectionError("Connection refused"),
            mock_200,
        ]

        result = _post_graphql(
            mock_session,
            operation_name="test",
            query="query { test }",
            variables={},
            max_retries=3,
        )

        assert result == {"data": {"result": True}}
        assert mock_session.post.call_count == 2
        mock_sleep.assert_called_once()


# ---------------------------------------------------------------------------
# TestDiscoverStores
# ---------------------------------------------------------------------------

class TestDiscoverStores:
    """Tests for discover_stores function."""

    @patch('src.scrapers.homedepot._post_graphql')
    def test_multi_state_fetch(self, mock_post, mock_session, yaml_config):
        """Test discovery across multiple states."""
        # Only mock 2 states for speed
        ga_response = {
            "data": {
                "storeDirectoryByState": {
                    "stateName": "Georgia",
                    "storesInfo": [
                        {
                            "storeName": "Cumberland",
                            "url": "https://www.homedepot.com/l/Cumberland/GA/Atlanta/30339/121",
                            "phone": "(770)432-9930",
                            "address": {
                                "street": "2450 Cumberland Pkwy",
                                "city": "Atlanta",
                                "state": "GA",
                                "postalCode": "30339",
                                "county": "Cobb"
                            }
                        }
                    ]
                }
            }
        }
        tx_response = {
            "data": {
                "storeDirectoryByState": {
                    "stateName": "Texas",
                    "storesInfo": [
                        {
                            "storeName": "El Paso",
                            "url": "https://www.homedepot.com/l/El-Paso/TX/El-Paso/79928/428",
                            "phone": "(915)600-1100",
                            "address": {
                                "street": "12611 State Street",
                                "city": "El Paso",
                                "state": "TX",
                                "postalCode": "79928",
                                "county": "El Paso"
                            }
                        }
                    ]
                }
            }
        }

        # Return response based on state variable
        def side_effect(session, operation_name, query, variables, **kwargs):
            state = variables.get("state")
            if state == "GA":
                return ga_response
            if state == "TX":
                return tx_response
            # Return empty for all other states
            return {
                "data": {
                    "storeDirectoryByState": {
                        "stateName": state,
                        "storesInfo": []
                    }
                }
            }

        mock_post.side_effect = side_effect
        counter = RequestCounter()

        results = discover_stores(
            mock_session, "homedepot", yaml_config, counter
        )

        # Should find 2 stores (one from GA, one from TX)
        assert len(results) == 2
        store_ids = {s["store_id"] for s in results}
        assert "121" in store_ids
        assert "428" in store_ids

    @patch('src.scrapers.homedepot._post_graphql')
    def test_store_id_extraction_from_url(self, mock_post, mock_session, yaml_config):
        """Test that store_id is correctly extracted from URL path."""
        mock_post.return_value = {
            "data": {
                "storeDirectoryByState": {
                    "stateName": "Alaska",
                    "storesInfo": [
                        {
                            "storeName": "Anchorage",
                            "url": "https://www.homedepot.com/l/Anchorage/AK/Anchorage/99515/4920",
                            "phone": "(907)365-5000",
                            "address": {
                                "street": "100 E Tudor Rd",
                                "city": "Anchorage",
                                "state": "AK",
                                "postalCode": "99515",
                                "county": "Anchorage"
                            }
                        }
                    ]
                }
            }
        }
        counter = RequestCounter()

        results = discover_stores(
            mock_session, "homedepot", yaml_config, counter
        )

        assert results[0]["store_id"] == "4920"

    @patch('src.scrapers.homedepot._post_graphql')
    def test_empty_state_handling(self, mock_post, mock_session, yaml_config):
        """Test that empty state responses are handled gracefully."""
        mock_post.return_value = {
            "data": {
                "storeDirectoryByState": {
                    "stateName": "Wyoming",
                    "storesInfo": []
                }
            }
        }
        counter = RequestCounter()

        results = discover_stores(
            mock_session, "homedepot", yaml_config, counter
        )

        # Empty stores from all 54 states
        assert len(results) == 0

    @patch('src.scrapers.homedepot._post_graphql')
    def test_failed_state_request(self, mock_post, mock_session, yaml_config):
        """Test that failed state requests are skipped gracefully."""
        mock_post.return_value = None  # Simulate failed request
        counter = RequestCounter()

        results = discover_stores(
            mock_session, "homedepot", yaml_config, counter
        )

        assert len(results) == 0

    @patch('src.scrapers.homedepot._post_graphql')
    def test_county_preserved_in_results(self, mock_post, mock_session, yaml_config):
        """Test that county from state directory is preserved in discovery results."""
        mock_post.return_value = {
            "data": {
                "storeDirectoryByState": {
                    "stateName": "Georgia",
                    "storesInfo": [
                        {
                            "storeName": "Cumberland",
                            "url": "https://www.homedepot.com/l/Cumberland/GA/Atlanta/30339/121",
                            "phone": "(770)432-9930",
                            "address": {
                                "street": "2450 Cumberland Pkwy",
                                "city": "Atlanta",
                                "state": "GA",
                                "postalCode": "30339",
                                "county": "Cobb"
                            }
                        }
                    ]
                }
            }
        }
        counter = RequestCounter()

        results = discover_stores(
            mock_session, "homedepot", yaml_config, counter
        )

        assert results[0]["county"] == "Cobb"


# ---------------------------------------------------------------------------
# TestExtractStoreDetails
# ---------------------------------------------------------------------------

class TestExtractStoreDetails:
    """Tests for extract_store_details function."""

    @patch('src.scrapers.homedepot._post_graphql')
    def test_full_data_parsing(self, mock_post, mock_session,
                                sample_store_search_response, yaml_config):
        """Test extraction with all fields populated."""
        mock_post.return_value = sample_store_search_response
        counter = RequestCounter()

        item = {
            "store_id": "121",
            "name": "Cumberland",
            "county": "Cobb",
        }

        result = extract_store_details(
            mock_session, item, "homedepot", yaml_config, counter
        )

        assert result is not None
        assert result.store_id == "121"
        assert result.name == "Cumberland"
        assert result.latitude == 33.862126
        assert result.longitude == -84.476161
        assert result.store_type == "retail"
        assert result.phone == "(770)432-9930"
        assert result.hours_mon == "6:00-22:00"
        assert result.hours_sun == "8:00-20:00"
        assert result.service_tool_rental is True
        assert result.service_hd_moving is False
        assert result.flag_bopis is True
        assert result.timezone == "EST5EDT"

    @patch('src.scrapers.homedepot._post_graphql')
    def test_county_merging_from_phase1(self, mock_post, mock_session,
                                         sample_store_search_response, yaml_config):
        """Test that county from Phase 1 item is merged into result."""
        mock_post.return_value = sample_store_search_response
        counter = RequestCounter()

        item = {
            "store_id": "121",
            "name": "Cumberland",
            "county": "Cobb",  # This comes from Phase 1
        }

        result = extract_store_details(
            mock_session, item, "homedepot", yaml_config, counter
        )

        assert result.county == "Cobb"

    @patch('src.scrapers.homedepot._post_graphql')
    def test_missing_optional_fields(self, mock_post, mock_session, yaml_config):
        """Test extraction with missing optional fields."""
        response = {
            "data": {
                "storeSearch": {
                    "stores": [
                        {
                            "storeId": "0999",
                            "name": "Test Store",
                            "address": {
                                "street": "123 Test St",
                                "city": "Testville",
                                "state": "TX",
                                "postalCode": "75001",
                                "country": "US"
                            },
                            "coordinates": None,
                            "services": None,
                            "storeHours": None,
                            "storeDetailsPageLink": "/l/Test/TX/Testville/75001/999",
                            "storeType": None,
                            "proDeskPhone": None,
                            "phone": "(555)000-0000",
                            "toolRentalPhone": None,
                            "storeServicesPhone": None,
                            "flags": None,
                            "storeTimeZone": None,
                            "proDeskHours": None,
                            "toolRentalHours": None,
                            "curbsidePickupHours": None
                        }
                    ]
                }
            }
        }
        mock_post.return_value = response
        counter = RequestCounter()

        item = {"store_id": "999", "name": "Test Store", "county": ""}

        result = extract_store_details(
            mock_session, item, "homedepot", yaml_config, counter
        )

        assert result is not None
        assert result.store_id == "999"
        assert result.latitude is None
        assert result.longitude is None
        assert result.service_load_n_go is False
        assert result.hours_mon == ""
        assert result.flag_bopis is False

    @patch('src.scrapers.homedepot._post_graphql')
    def test_failed_api_call(self, mock_post, mock_session, yaml_config):
        """Test that None is returned when API call fails."""
        mock_post.return_value = None
        counter = RequestCounter()

        item = {"store_id": "121", "name": "Cumberland", "county": "Cobb"}

        result = extract_store_details(
            mock_session, item, "homedepot", yaml_config, counter
        )

        assert result is None

    @patch('src.scrapers.homedepot._post_graphql')
    def test_store_id_zero_padding(self, mock_post, mock_session,
                                    sample_store_search_response, yaml_config):
        """Test that store_id is zero-padded to 4 digits for API call."""
        mock_post.return_value = sample_store_search_response
        counter = RequestCounter()

        item = {"store_id": "121", "name": "Cumberland", "county": "Cobb"}

        extract_store_details(
            mock_session, item, "homedepot", yaml_config, counter
        )

        # Verify the storeSearchInput was zero-padded
        call_args = mock_post.call_args
        variables = call_args[1].get("variables") or call_args[0][3]
        assert variables["storeSearchInput"] == "0121"

    @patch('src.scrapers.homedepot._post_graphql')
    def test_empty_stores_in_response(self, mock_post, mock_session, yaml_config):
        """Test handling of empty stores array in response."""
        mock_post.return_value = {
            "data": {
                "storeSearch": {
                    "stores": []
                }
            }
        }
        counter = RequestCounter()

        item = {"store_id": "9999", "name": "Ghost Store", "county": ""}

        result = extract_store_details(
            mock_session, item, "homedepot", yaml_config, counter
        )

        assert result is None

    @patch('src.scrapers.homedepot._post_graphql')
    def test_null_nested_response(self, mock_post, mock_session, yaml_config):
        """Test handling of null storeSearch in response (null nested object)."""
        mock_post.return_value = {
            "data": {
                "storeSearch": None
            }
        }
        counter = RequestCounter()

        item = {"store_id": "9999", "name": "Null Store", "county": ""}

        result = extract_store_details(
            mock_session, item, "homedepot", yaml_config, counter
        )

        assert result is None


# ---------------------------------------------------------------------------
# TestRun
# ---------------------------------------------------------------------------

class TestRun:
    """Tests for the run() entry point."""

    @patch('src.scrapers.homedepot.ScrapeRunner')
    def test_run_creates_context_and_runner(self, mock_runner_class, mock_session, yaml_config):
        """Test that run() creates a ScraperContext and ScrapeRunner."""
        mock_runner = Mock()
        mock_runner.run_with_checkpoints.return_value = {
            "stores": [{"store_id": "121"}],
            "count": 1,
            "checkpoints_used": False
        }
        mock_runner_class.return_value = mock_runner

        result = run(mock_session, yaml_config, retailer="homedepot")

        assert result["count"] == 1
        assert result["stores"][0]["store_id"] == "121"
        mock_runner_class.assert_called_once()
        mock_runner.run_with_checkpoints.assert_called_once()

    @patch('src.scrapers.homedepot.ScrapeRunner')
    def test_run_passes_resume_and_limit(self, mock_runner_class, mock_session, yaml_config):
        """Test that run() passes resume and limit through ScraperContext."""
        mock_runner = Mock()
        mock_runner.run_with_checkpoints.return_value = {
            "stores": [], "count": 0, "checkpoints_used": True
        }
        mock_runner_class.return_value = mock_runner

        run(mock_session, yaml_config, retailer="homedepot", resume=True, limit=50)

        # Verify ScraperContext was created with correct params
        context_arg = mock_runner_class.call_args[0][0]
        assert context_arg.resume is True
        assert context_arg.limit == 50
        assert context_arg.use_rich_cache is True

    @patch('src.scrapers.homedepot.ScrapeRunner')
    def test_run_uses_rich_cache(self, mock_runner_class, mock_session, yaml_config):
        """Test that run() enables RichURLCache for Phase 1 dict caching."""
        mock_runner = Mock()
        mock_runner.run_with_checkpoints.return_value = {
            "stores": [], "count": 0, "checkpoints_used": False
        }
        mock_runner_class.return_value = mock_runner

        run(mock_session, yaml_config)

        context_arg = mock_runner_class.call_args[0][0]
        assert context_arg.use_rich_cache is True

    @patch('src.scrapers.homedepot.ScrapeRunner')
    def test_run_passes_correct_functions(self, mock_runner_class, mock_session, yaml_config):
        """Test that run() passes discover_stores and extract_store_details."""
        mock_runner = Mock()
        mock_runner.run_with_checkpoints.return_value = {
            "stores": [], "count": 0, "checkpoints_used": False
        }
        mock_runner_class.return_value = mock_runner

        run(mock_session, yaml_config)

        call_kwargs = mock_runner.run_with_checkpoints.call_args[1]
        assert call_kwargs["url_discovery_func"] == discover_stores
        assert call_kwargs["extraction_func"] == extract_store_details
        # item_key_func should extract store_id from dict
        key_func = call_kwargs["item_key_func"]
        assert key_func({"store_id": "121", "name": "Test"}) == "121"
