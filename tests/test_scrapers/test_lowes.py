"""Unit tests for Lowe's scraper."""
# pylint: disable=no-member

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.scrapers.lowes import (
    LowesStore,
    _extract_json_from_html,
    _format_hours,
    _parse_store_data,
    get_store_ids_from_state,
    get_all_store_ids,
    extract_store_details,
    run,
    reset_request_counter,
)
from config import lowes_config


# =============================================================================
# Sample Data Fixtures
# =============================================================================

SAMPLE_STORE_JSON = {
    "_id": "63994ee18b168758f99b3af1",
    "zip": "07724",
    "address": "118 Highway 35",
    "storeHours": [
        {
            "day": {"day": "Monday", "open": "06.00.00", "close": "21.00.00"},
            "label": "Monday",
            "open": "6:00 am",
            "close": "9:00 pm",
            "isCurrentDay": False,
            "isHoliday": False,
            "is24Open": False,
        },
        {
            "day": {"day": "Saturday", "open": "06.00.00", "close": "21.00.00"},
            "label": "Saturday",
            "open": "6:00 am",
            "close": "9:00 pm",
            "isCurrentDay": False,
            "isHoliday": False,
            "is24Open": False,
        },
    ],
    "city": "Eatontown",
    "bisName": "LOWE'S OF EATONTOWN, NJ",
    "phone": "(732) 544-5820",
    "storeName": "Eatontown Lowe's",
    "fax": "(732) 544-5821",
    "proServicesDesk": "(732) 544-5849",
    "proFax": "(732) 544-5823",
    "toolPhone": "",
    "lat": "40.296715",
    "long": "-74.056353",
    "timeZone": "America/New_York",
    "storeDescription": "Working on a project?",
    "storeFeature": "Garden Center,Key Copy,Dog-Friendly,Pickup Lockers,Truck Delivery",
    "corpNumber": "29",
    "areaNumber": "1243",
    "regionNumber": "30",
    "storeType": "1",
    "storeStatusCd": "1",
    "openDate": "2005-10-12",
    "country": "US",
    "id": "1548",
    "state": "NJ",
    "stateFullName": "New Jersey",
    "pageUrl": "https://www.lowes.com/store/NJ-Eatontown/1548",
    "store_name": "Eatontown Lowe's",
    "bis_name": "LOWE'S OF EATONTOWN, NJ",
}


def _build_html_with_store_json(store_json):
    """Build a realistic HTML page with embedded store JSON."""
    json_str = json.dumps(store_json)
    return f"""
    <html><head><title>Lowe's Store</title></head>
    <body>
    <div id="app">
    <script>window.__PRELOADED_STATE__ = {{"storeDetail": {json_str}}}</script>
    </div>
    </body></html>
    """


def _build_state_directory_html(store_ids, state_code="NJ"):
    """Build a realistic state directory page HTML."""
    links = ""
    embedded = ""
    for sid in store_ids:
        links += f'<a href="/store/{state_code}-City/{sid}">Store {sid}</a>\n'
        embedded += f'{{"id": "{sid}", "storeName": "Store {sid}"}}\n'
    return f"""
    <html><body>
    <div class="store-list">
    {links}
    </div>
    <script>var storeData = [{embedded}];</script>
    </body></html>
    """


# =============================================================================
# LowesStore Dataclass Tests
# =============================================================================


class TestLowesStore:
    """Tests for LowesStore dataclass."""

    def test_to_dict(self):
        """Test dictionary conversion contains all fields."""
        store = LowesStore(
            store_id="1548",
            name="Eatontown Lowe's",
            street_address="118 Highway 35",
            city="Eatontown",
            state="NJ",
            state_full_name="New Jersey",
            zip="07724",
            country="US",
            latitude="40.296715",
            longitude="-74.056353",
            phone="(732) 544-5820",
            fax="(732) 544-5821",
            timezone="America/New_York",
            store_type="1",
            store_status="1",
            open_date="2005-10-12",
            features="Garden Center,Key Copy",
            hours='[{"day": "Monday", "open": "6:00 am", "close": "9:00 pm"}]',
            url="https://www.lowes.com/store/NJ-Eatontown/1548",
            scraped_at="2026-02-05T12:00:00",
        )
        result = store.to_dict()

        assert result["store_id"] == "1548"
        assert result["name"] == "Eatontown Lowe's"
        assert result["city"] == "Eatontown"
        assert result["state"] == "NJ"
        assert result["state_full_name"] == "New Jersey"
        assert result["zip"] == "07724"
        assert result["latitude"] == "40.296715"
        assert result["longitude"] == "-74.056353"
        assert result["features"] == "Garden Center,Key Copy"
        assert "corp_number" in result
        assert "area_number" in result

    def test_to_dict_with_none_coordinates(self):
        """Test dictionary conversion handles None latitude/longitude."""
        store = LowesStore(
            store_id="1000",
            name="Test Store",
            street_address="123 Main St",
            city="Anytown",
            state="TX",
            state_full_name="Texas",
            zip="75001",
            country="US",
            latitude=None,
            longitude=None,
            phone="",
            fax="",
            timezone="",
            store_type="1",
            store_status="1",
            open_date="",
            features="",
            hours=None,
            url="",
        )
        result = store.to_dict()
        assert result["latitude"] is None
        assert result["longitude"] is None

    def test_default_values(self):
        """Test default values are set correctly."""
        store = LowesStore(
            store_id="1000",
            name="Test",
            street_address="123",
            city="City",
            state="TX",
            state_full_name="Texas",
            zip="75001",
            country="US",
            latitude=None,
            longitude=None,
            phone="",
            fax="",
            timezone="",
            store_type="1",
            store_status="1",
            open_date="",
            features="",
            hours=None,
            url="",
        )
        assert store.corp_number == ""
        assert store.area_number == ""
        assert store.region_number == ""
        assert store.scraped_at == ""


# =============================================================================
# JSON Extraction Tests
# =============================================================================


class TestExtractJsonFromHtml:
    """Tests for _extract_json_from_html function."""

    def test_valid_embedded_json(self):
        """Test extraction from valid HTML with embedded store JSON."""
        html = _build_html_with_store_json(SAMPLE_STORE_JSON)
        result = _extract_json_from_html(html)

        assert result is not None
        assert result["id"] == "1548"
        assert result["storeName"] == "Eatontown Lowe's"
        assert result["state"] == "NJ"

    def test_no_marker_returns_none(self):
        """Test returns None when _id marker is not found."""
        html = "<html><body>No store data here</body></html>"
        result = _extract_json_from_html(html)
        assert result is None

    def test_empty_html_returns_none(self):
        """Test returns None for empty HTML."""
        result = _extract_json_from_html("")
        assert result is None

    def test_malformed_json_returns_none(self):
        """Test returns None when JSON is malformed."""
        html = 'prefix {"_id":"abc", broken json here} suffix'
        result = _extract_json_from_html(html)
        # The brace matching will find a string, but json.loads will fail.
        # The function should catch the JSONDecodeError and return None.
        assert result is None

    def test_nested_braces(self):
        """Test extraction handles nested JSON objects correctly."""
        nested_json = {
            "_id": "test123",
            "id": "1000",
            "storeName": "Test Store",
            "nested": {"key": "value", "deeper": {"a": 1}},
        }
        html = f'<div>some content {json.dumps(nested_json)} more content</div>'
        result = _extract_json_from_html(html)

        assert result is not None
        assert result["id"] == "1000"
        assert result["nested"]["deeper"]["a"] == 1

    def test_marker_without_opening_brace_nearby(self):
        """Test returns None when no opening brace within lookback distance."""
        # Put 200+ chars between brace and marker
        padding = "x" * 200
        html = f'{{{padding}"_id":"abc"}}'
        result = _extract_json_from_html(html)
        # Should not find it because lookback is only 100 chars
        assert result is None

    def test_braces_inside_string_values(self):
        """Test extraction handles braces inside quoted string values."""
        data = {
            "_id": "test123",
            "id": "1000",
            "storeName": "Test Store",
            "storeDescription": "Welcome to {your} local Lowe's",
            "address": "123 {Suite A} Rd",
        }
        html = f'<div>{json.dumps(data)}</div>'
        result = _extract_json_from_html(html)

        assert result is not None
        assert result["id"] == "1000"
        assert "{your}" in result["storeDescription"]
        assert "{Suite A}" in result["address"]

    def test_multiple_json_objects_finds_first(self):
        """Test extracts the first JSON object with the _id marker."""
        json1 = {"_id": "first", "id": "1001", "storeName": "First"}
        json2 = {"_id": "second", "id": "1002", "storeName": "Second"}
        html = f'prefix {json.dumps(json1)} middle {json.dumps(json2)} suffix'
        result = _extract_json_from_html(html)

        assert result is not None
        assert result["id"] == "1001"


# =============================================================================
# Hours Formatting Tests
# =============================================================================


class TestFormatHours:
    """Tests for _format_hours function."""

    def test_valid_hours(self):
        """Test formatting standard business hours."""
        hours = [
            {
                "day": {"day": "Monday", "open": "06.00.00", "close": "21.00.00"},
                "label": "Monday",
                "open": "6:00 am",
                "close": "9:00 pm",
                "isCurrentDay": False,
                "isHoliday": False,
                "is24Open": False,
            },
            {
                "day": {"day": "Tuesday", "open": "06.00.00", "close": "21.00.00"},
                "label": "Tuesday",
                "open": "6:00 am",
                "close": "9:00 pm",
                "isCurrentDay": False,
                "isHoliday": False,
                "is24Open": False,
            },
        ]
        result = _format_hours(hours)
        parsed = json.loads(result)

        assert len(parsed) == 2
        assert parsed[0]["day"] == "Monday"
        assert parsed[0]["open"] == "6:00 am"
        assert parsed[0]["close"] == "9:00 pm"
        assert parsed[0]["is24Open"] is False
        assert parsed[0]["isHoliday"] is False

    def test_empty_hours(self):
        """Test returns None for empty hours list."""
        assert _format_hours([]) is None
        assert _format_hours(None) is None

    def test_24_hour_store(self):
        """Test formatting for 24-hour stores."""
        hours = [
            {
                "day": {"day": "Monday", "open": "00.00.00", "close": "23.59.59"},
                "label": "Monday",
                "open": "12:00 am",
                "close": "11:59 pm",
                "isCurrentDay": False,
                "isHoliday": False,
                "is24Open": True,
            },
        ]
        result = _format_hours(hours)
        parsed = json.loads(result)

        assert parsed[0]["is24Open"] is True
        assert parsed[0]["open"] == "Open 24 hours"
        assert parsed[0]["close"] == ""

    def test_holiday_hours(self):
        """Test holiday flag is preserved."""
        hours = [
            {
                "day": {"day": "Thursday", "open": "08.00.00", "close": "18.00.00"},
                "label": "Thanksgiving",
                "open": "8:00 am",
                "close": "6:00 pm",
                "isCurrentDay": False,
                "isHoliday": True,
                "is24Open": False,
            },
        ]
        result = _format_hours(hours)
        parsed = json.loads(result)

        assert parsed[0]["isHoliday"] is True

    def test_invalid_day_entry_skipped(self):
        """Test entries with non-dict day info are skipped."""
        hours = [
            {
                "day": "not a dict",
                "label": "Bad",
                "open": "6:00 am",
                "close": "9:00 pm",
                "is24Open": False,
            },
        ]
        result = _format_hours(hours)
        assert result is None


# =============================================================================
# Parse Store Data Tests
# =============================================================================


class TestParseStoreData:
    """Tests for _parse_store_data function."""

    def test_valid_store_data(self):
        """Test parsing complete store data."""
        store = _parse_store_data(SAMPLE_STORE_JSON, "1548")

        assert store is not None
        assert store.store_id == "1548"
        assert store.name == "Eatontown Lowe's"
        assert store.street_address == "118 Highway 35"
        assert store.city == "Eatontown"
        assert store.state == "NJ"
        assert store.state_full_name == "New Jersey"
        assert store.zip == "07724"
        assert store.country == "US"
        assert store.latitude == "40.296715"
        assert store.longitude == "-74.056353"
        assert store.phone == "(732) 544-5820"
        assert store.fax == "(732) 544-5821"
        assert store.timezone == "America/New_York"
        assert store.store_type == "1"
        assert store.store_status == "1"
        assert store.open_date == "2005-10-12"
        assert "Garden Center" in store.features
        assert store.corp_number == "29"
        assert store.area_number == "1243"
        assert store.region_number == "30"
        assert store.url == "https://www.lowes.com/store/NJ-Eatontown/1548"

    def test_missing_store_name_returns_none(self):
        """Test returns None when storeName is missing."""
        data = {"id": "1548", "city": "Eatontown"}
        result = _parse_store_data(data, "1548")
        assert result is None

    def test_uses_fallback_store_name(self):
        """Test falls back to store_name when storeName is missing."""
        data = {
            "id": "1548",
            "store_name": "Fallback Name",
            "city": "Eatontown",
            "state": "NJ",
        }
        result = _parse_store_data(data, "1548")
        assert result is not None
        assert result.name == "Fallback Name"

    def test_uses_passed_store_id_as_fallback(self):
        """Test uses the passed store_id when 'id' is missing from data."""
        data = {
            "storeName": "Test Store",
            "city": "Anytown",
        }
        result = _parse_store_data(data, "9999")
        assert result is not None
        assert result.store_id == "9999"

    def test_hours_are_formatted(self):
        """Test that store hours are formatted to JSON string."""
        store = _parse_store_data(SAMPLE_STORE_JSON, "1548")
        assert store is not None
        assert store.hours is not None

        parsed_hours = json.loads(store.hours)
        assert len(parsed_hours) == 2
        assert parsed_hours[0]["day"] == "Monday"

    def test_empty_optional_fields(self):
        """Test handles missing optional fields gracefully."""
        data = {
            "id": "1000",
            "storeName": "Minimal Store",
        }
        result = _parse_store_data(data, "1000")
        assert result is not None
        assert result.phone == ""
        assert result.fax == ""
        assert result.timezone == ""
        assert result.features == ""
        assert result.country == "US"  # Default


# =============================================================================
# State Directory Parsing Tests
# =============================================================================


class TestGetStoreIdsFromState:
    """Tests for get_store_ids_from_state function."""

    def setup_method(self):
        """Reset request counter before each test."""
        reset_request_counter()

    @patch("src.scrapers.lowes.utils.get_with_retry")
    @patch("src.scrapers.lowes.check_pause_logic")
    def test_extracts_store_ids_from_links(self, mock_pause, mock_get):
        """Test extraction of store IDs from href links."""
        html = _build_state_directory_html(["1548", "1234", "5678"])
        mock_response = Mock()
        mock_response.text = html
        mock_get.return_value = mock_response

        session = Mock()
        ids = get_store_ids_from_state(session, "New-Jersey", "NJ")

        assert set(ids) == {"1548", "1234", "5678"}

    @patch("src.scrapers.lowes.utils.get_with_retry")
    @patch("src.scrapers.lowes.check_pause_logic")
    def test_deduplicates_ids(self, mock_pause, mock_get):
        """Test that duplicate IDs from links and embedded data are deduplicated."""
        # Build HTML with same ID in both links and embedded data
        html = """
        <a href="/store/NJ-City/1548">Store</a>
        <script>{"id": "1548", "storeName": "Store 1548"}</script>
        """
        mock_response = Mock()
        mock_response.text = html
        mock_get.return_value = mock_response

        session = Mock()
        ids = get_store_ids_from_state(session, "New-Jersey", "NJ")

        assert ids.count("1548") == 1

    @patch("src.scrapers.lowes.utils.get_with_retry")
    def test_failed_request_returns_empty(self, mock_get):
        """Test returns empty list when request fails."""
        mock_get.return_value = None

        session = Mock()
        ids = get_store_ids_from_state(session, "New-Jersey", "NJ")

        assert ids == []

    @patch("src.scrapers.lowes.utils.get_with_retry")
    @patch("src.scrapers.lowes.check_pause_logic")
    def test_no_stores_returns_empty(self, mock_pause, mock_get):
        """Test returns empty list when no store IDs found."""
        mock_response = Mock()
        mock_response.text = "<html><body>No stores</body></html>"
        mock_get.return_value = mock_response

        session = Mock()
        ids = get_store_ids_from_state(session, "Alaska", "AK")

        assert ids == []


# =============================================================================
# Get All Store IDs Tests
# =============================================================================


class TestGetAllStoreIds:
    """Tests for get_all_store_ids function."""

    def setup_method(self):
        """Reset request counter before each test."""
        reset_request_counter()

    @patch("src.scrapers.lowes.get_store_ids_from_state")
    @patch("src.scrapers.lowes.utils.random_delay")
    @patch("src.scrapers.lowes.utils.select_delays")
    def test_aggregates_across_states(self, mock_select, mock_delay, mock_get_state):
        """Test aggregation of store IDs across multiple states."""
        mock_select.return_value = (1.0, 2.0)
        mock_get_state.side_effect = [
            ["1001", "1002"],
            ["1003", "1004"],
        ]
        yaml_config = {"proxy": {"mode": "direct"}}

        # Limit to 2 states for test speed
        result = get_all_store_ids(
            Mock(), "lowes", yaml_config, states=["NJ", "NY"]
        )

        assert len(result) == 4
        assert set(result) == {"1001", "1002", "1003", "1004"}

    @patch("src.scrapers.lowes.get_store_ids_from_state")
    @patch("src.scrapers.lowes.utils.random_delay")
    @patch("src.scrapers.lowes.utils.select_delays")
    def test_deduplicates_across_states(self, mock_select, mock_delay, mock_get_state):
        """Test deduplication when same store appears in multiple states."""
        mock_select.return_value = (1.0, 2.0)
        mock_get_state.side_effect = [
            ["1001", "1002"],
            ["1002", "1003"],  # 1002 is a duplicate
        ]
        yaml_config = {"proxy": {"mode": "direct"}}

        result = get_all_store_ids(
            Mock(), "lowes", yaml_config, states=["NJ", "NY"]
        )

        assert len(result) == 3
        assert "1002" in result

    @patch("src.scrapers.lowes.get_store_ids_from_state")
    @patch("src.scrapers.lowes.utils.random_delay")
    @patch("src.scrapers.lowes.utils.select_delays")
    def test_filters_by_state(self, mock_select, mock_delay, mock_get_state):
        """Test state filter limits discovery to specified states."""
        mock_select.return_value = (1.0, 2.0)
        mock_get_state.return_value = ["1001"]
        yaml_config = {"proxy": {"mode": "direct"}}

        get_all_store_ids(
            Mock(), "lowes", yaml_config, states=["TX"]
        )

        # Should only be called once (for TX)
        assert mock_get_state.call_count == 1
        call_args = mock_get_state.call_args
        assert call_args[0][1] == "Texas"
        assert call_args[0][2] == "TX"

    @patch("src.scrapers.lowes.get_store_ids_from_state")
    @patch("src.scrapers.lowes.utils.random_delay")
    @patch("src.scrapers.lowes.utils.select_delays")
    def test_returns_sorted_ids(self, mock_select, mock_delay, mock_get_state):
        """Test IDs are returned sorted."""
        mock_select.return_value = (1.0, 2.0)
        mock_get_state.return_value = ["1003", "1001", "1002"]
        yaml_config = {"proxy": {"mode": "direct"}}

        result = get_all_store_ids(
            Mock(), "lowes", yaml_config, states=["NJ"]
        )

        assert result == sorted(result)


# =============================================================================
# Store Detail Extraction Tests
# =============================================================================


class TestExtractStoreDetails:
    """Tests for extract_store_details function."""

    def setup_method(self):
        """Reset request counter before each test."""
        reset_request_counter()

    @patch("src.scrapers.lowes.utils.get_with_retry")
    @patch("src.scrapers.lowes.check_pause_logic")
    def test_extracts_complete_store(self, mock_pause, mock_get):
        """Test successful extraction of full store data."""
        html = _build_html_with_store_json(SAMPLE_STORE_JSON)
        mock_response = Mock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        session = Mock()
        store = extract_store_details(session, "1548")

        assert store is not None
        assert store.store_id == "1548"
        assert store.name == "Eatontown Lowe's"
        assert store.state == "NJ"

    @patch("src.scrapers.lowes.utils.get_with_retry")
    def test_request_failure_returns_none(self, mock_get):
        """Test returns None when request fails."""
        mock_get.return_value = None

        session = Mock()
        store = extract_store_details(session, "9999")

        assert store is None

    @patch("src.scrapers.lowes.utils.get_with_retry")
    def test_404_returns_none(self, mock_get):
        """Test returns None for 404 responses (handled by get_with_retry)."""
        # get_with_retry returns None for all 4xx errors including 404
        mock_get.return_value = None

        session = Mock()
        store = extract_store_details(session, "0000")

        assert store is None

    @patch("src.scrapers.lowes.utils.get_with_retry")
    @patch("src.scrapers.lowes.check_pause_logic")
    def test_no_embedded_json_returns_none(self, mock_pause, mock_get):
        """Test returns None when page has no embedded JSON."""
        mock_response = Mock()
        mock_response.text = "<html><body>No store data</body></html>"
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        session = Mock()
        store = extract_store_details(session, "1548")

        assert store is None


# =============================================================================
# Run Entry Point Tests
# =============================================================================


class TestRun:
    """Tests for the run() entry point."""

    def setup_method(self):
        """Reset request counter before each test."""
        reset_request_counter()

    @patch("src.scrapers.lowes.utils.validate_stores_batch")
    @patch("src.scrapers.lowes.utils.save_checkpoint")
    @patch("src.scrapers.lowes.utils.random_delay")
    @patch("src.scrapers.lowes.extract_store_details")
    @patch("src.scrapers.lowes.URLCache")
    @patch("src.scrapers.lowes.get_all_store_ids")
    @patch("src.scrapers.lowes.utils.select_delays")
    def test_full_run_with_discovery(
        self, mock_delays, mock_discover, mock_cache_cls,
        mock_extract, mock_delay, mock_save_cp, mock_validate
    ):
        """Test full run with discovery and extraction."""
        mock_delays.return_value = (1.0, 2.0)
        mock_discover.return_value = ["1548", "1234"]

        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_store = Mock()
        mock_store.to_dict.return_value = {
            "store_id": "1548",
            "name": "Test Store",
            "street_address": "123 Main",
            "city": "City",
            "state": "NJ",
        }
        mock_extract.side_effect = [mock_store, mock_store]
        mock_validate.return_value = {"valid": 2, "total": 2, "warning_count": 0}

        yaml_config = {
            "proxy": {"mode": "direct"},
            "checkpoint_interval": 100,
        }

        result = run(Mock(), yaml_config, retailer="lowes")

        assert result["count"] == 2
        assert len(result["stores"]) == 2
        assert result["checkpoints_used"] is False

    @patch("src.scrapers.lowes.utils.validate_stores_batch")
    @patch("src.scrapers.lowes.utils.save_checkpoint")
    @patch("src.scrapers.lowes.utils.random_delay")
    @patch("src.scrapers.lowes.extract_store_details")
    @patch("src.scrapers.lowes.URLCache")
    @patch("src.scrapers.lowes.utils.select_delays")
    def test_run_with_cached_ids(
        self, mock_delays, mock_cache_cls,
        mock_extract, mock_delay, mock_save_cp, mock_validate
    ):
        """Test run uses cached store IDs when available."""
        mock_delays.return_value = (1.0, 2.0)

        mock_cache = Mock()
        mock_cache.get.return_value = ["1548"]
        mock_cache_cls.return_value = mock_cache

        mock_store = Mock()
        mock_store.to_dict.return_value = {
            "store_id": "1548", "name": "Test", "street_address": "123",
            "city": "City", "state": "NJ",
        }
        mock_extract.return_value = mock_store
        mock_validate.return_value = {"valid": 1, "total": 1, "warning_count": 0}

        yaml_config = {
            "proxy": {"mode": "direct"},
            "checkpoint_interval": 100,
        }

        result = run(Mock(), yaml_config, retailer="lowes")

        assert result["count"] == 1

    @patch("src.scrapers.lowes.utils.validate_stores_batch")
    @patch("src.scrapers.lowes.utils.save_checkpoint")
    @patch("src.scrapers.lowes.utils.load_checkpoint")
    @patch("src.scrapers.lowes.utils.random_delay")
    @patch("src.scrapers.lowes.extract_store_details")
    @patch("src.scrapers.lowes.URLCache")
    @patch("src.scrapers.lowes.utils.select_delays")
    def test_run_with_resume(
        self, mock_delays, mock_cache_cls,
        mock_extract, mock_delay, mock_load_cp, mock_save_cp, mock_validate
    ):
        """Test run resumes from checkpoint."""
        mock_delays.return_value = (1.0, 2.0)

        mock_cache = Mock()
        mock_cache.get.return_value = ["1548", "1234", "5678"]
        mock_cache_cls.return_value = mock_cache

        # Checkpoint has 1548 already done
        mock_load_cp.return_value = {
            "stores": [{"store_id": "1548", "name": "Done", "street_address": "x",
                        "city": "y", "state": "NJ"}],
            "completed_ids": ["1548"],
        }

        mock_store = Mock()
        mock_store.to_dict.return_value = {
            "store_id": "1234", "name": "New", "street_address": "x",
            "city": "y", "state": "NY",
        }
        mock_extract.return_value = mock_store
        mock_validate.return_value = {"valid": 3, "total": 3, "warning_count": 0}

        yaml_config = {
            "proxy": {"mode": "direct"},
            "checkpoint_interval": 100,
        }

        result = run(Mock(), yaml_config, retailer="lowes", resume=True)

        assert result["checkpoints_used"] is True
        # Should process 1234 and 5678, plus the already-done 1548
        assert result["count"] == 3

    @patch("src.scrapers.lowes.utils.validate_stores_batch")
    @patch("src.scrapers.lowes.utils.save_checkpoint")
    @patch("src.scrapers.lowes.utils.random_delay")
    @patch("src.scrapers.lowes.extract_store_details")
    @patch("src.scrapers.lowes.URLCache")
    @patch("src.scrapers.lowes.utils.select_delays")
    def test_run_with_limit(
        self, mock_delays, mock_cache_cls,
        mock_extract, mock_delay, mock_save_cp, mock_validate
    ):
        """Test run respects store limit."""
        mock_delays.return_value = (1.0, 2.0)

        mock_cache = Mock()
        mock_cache.get.return_value = ["1001", "1002", "1003", "1004", "1005"]
        mock_cache_cls.return_value = mock_cache

        mock_store = Mock()
        mock_store.to_dict.return_value = {
            "store_id": "x", "name": "T", "street_address": "a",
            "city": "b", "state": "NJ",
        }
        mock_extract.return_value = mock_store
        mock_validate.return_value = {"valid": 2, "total": 2, "warning_count": 0}

        yaml_config = {
            "proxy": {"mode": "direct"},
            "checkpoint_interval": 100,
        }

        result = run(Mock(), yaml_config, retailer="lowes", limit=2)

        assert result["count"] == 2
        assert mock_extract.call_count == 2

    @patch("src.scrapers.lowes.get_all_store_ids")
    @patch("src.scrapers.lowes.URLCache")
    @patch("src.scrapers.lowes.utils.select_delays")
    def test_run_no_store_ids_returns_empty(self, mock_delays, mock_cache_cls, mock_discover):
        """Test run returns empty when no store IDs discovered."""
        mock_delays.return_value = (1.0, 2.0)

        mock_cache = Mock()
        mock_cache.get.return_value = None  # No cache
        mock_cache_cls.return_value = mock_cache

        mock_discover.return_value = []  # No stores found

        yaml_config = {
            "proxy": {"mode": "direct"},
            "checkpoint_interval": 100,
        }

        result = run(Mock(), yaml_config, retailer="lowes")

        assert result["count"] == 0
        assert result["stores"] == []


# =============================================================================
# Config Module Tests
# =============================================================================


class TestLowesConfig:
    """Tests for lowes_config module."""

    def test_states_list_complete(self):
        """Test that all 51 state/territory entries are present."""
        assert len(lowes_config.STATES) == 51

    def test_states_codes_unique(self):
        """Test all state codes are unique."""
        codes = [code for _, code in lowes_config.STATES]
        assert len(codes) == len(set(codes))

    def test_dc_included(self):
        """Test District of Columbia is included."""
        codes = [code for _, code in lowes_config.STATES]
        assert "DC" in codes

    def test_build_state_directory_url(self):
        """Test state directory URL construction."""
        url = lowes_config.build_state_directory_url("New-Jersey", "NJ")
        assert url == "https://www.lowes.com/Lowes-Stores/New-Jersey/NJ"

    def test_build_store_detail_url(self):
        """Test store detail URL construction."""
        url = lowes_config.build_store_detail_url("1548")
        assert url == "https://www.lowes.com/store/X-X/1548"

    def test_regex_patterns_valid(self):
        """Test regex patterns compile without errors."""
        import re
        re.compile(lowes_config.STORE_LINK_PATTERN)
        re.compile(lowes_config.EMBEDDED_STORE_ID_PATTERN)

    def test_store_link_pattern_matches(self):
        """Test store link regex matches expected format."""
        import re
        html = '<a href="/store/NJ-Eatontown/1548">Store</a>'
        matches = re.findall(lowes_config.STORE_LINK_PATTERN, html)
        assert matches == ["1548"]

    def test_embedded_id_pattern_matches(self):
        """Test embedded ID regex matches 4-digit IDs."""
        import re
        html = '{"id": "1548", "storeName": "Test"}'
        matches = re.findall(lowes_config.EMBEDDED_STORE_ID_PATTERN, html)
        assert matches == ["1548"]
