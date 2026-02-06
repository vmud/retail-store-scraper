"""Comprehensive tests for the Staples store scraper.

Tests cover:
  - StaplesStore dataclass and to_dict()
  - Phone formatting
  - Hours parsing from both APIs
  - Feature and service formatting
  - StaplesConnect store parsing
  - Store locator response parsing
  - Store data merging
  - Store number generation
  - Phase 1: Store number scanning (mocked)
  - Phase 2: ZIP code gap-fill (mocked)
  - Phase 3: Service enrichment (mocked)
  - Full run() integration (mocked)
"""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.scrapers.staples import (
    StaplesStore,
    _enrich_services,
    _format_features,
    _format_hours_locator,
    _format_hours_staplesconnect,
    _format_phone,
    _format_services,
    _generate_store_numbers,
    _merge_store_data,
    _parse_locator_store,
    _parse_staplesconnect_store,
    _scan_store_numbers,
    _search_stores_by_zip,
    _zip_code_gap_fill,
    run,
)
from config import staples_config as config


# ===========================================================================
# Test Fixtures: Mock API Responses (from design doc schemas)
# ===========================================================================

STAPLESCONNECT_STORE_RESPONSE = {
    "id": 1571,
    "address": {
        "address_1": "1100 State Route 35",
        "address_2": "STE A",
        "city": "Ocean Township",
        "region": "NJ",
        "postal_code": "07712",
        "country": "US",
        "latitude": 40.2395,
        "longitude": -74.0362,
        "urlAddress": "1100-state-route-35",
        "urlState": "nj",
        "urlCity": "ocean-township",
    },
    "name": "Staples Retail Store 1571 - Ocean Township NJ",
    "latitude": 40.2395,
    "longitude": -74.0362,
    "faxNumber": "7325172393",
    "phoneNumber": "7329189446",
    "storeTitle": "Staples Ocean Township, NJ",
    "storeNumber": "1571",
    "timezone": "America/New_York",
    "storeHours": [
        {
            "open24Hr": False,
            "close24Hr": False,
            "open": "08:00 AM",
            "close": "09:00 PM",
            "formattedStoreHours": "8:00 AM - 9:00 PM",
            "dayShort": "MON",
            "day": "MONDAY",
        },
        {
            "open24Hr": False,
            "close24Hr": False,
            "open": "08:00 AM",
            "close": "09:00 PM",
            "formattedStoreHours": "8:00 AM - 9:00 PM",
            "dayShort": "TUE",
            "day": "TUESDAY",
        },
        {
            "open24Hr": False,
            "close24Hr": True,
            "open": "",
            "close": "",
            "formattedStoreHours": "",
            "dayShort": "SUN",
            "day": "SUNDAY",
        },
    ],
    "plazaMall": "Plaza at Ocean",
    "publishedStatus": "ACTIVE",
    "storeRegion": "R230",
    "storeDistrict": "D155",
    "storeDivision": "Northeast",
    "storeServices": [
        {
            "serviceId": 1,
            "serviceName": "Print and Marketing Services",
            "serviceDescription": "Full service printing",
            "serviceImageUrl": "https://example.com/img.png",
            "serviceLandingPageUrl": "https://example.com/print",
            "active": True,
        },
        {
            "serviceId": 2,
            "serviceName": "Shredding Services",
            "serviceDescription": "Document shredding",
            "active": True,
        },
        {
            "serviceId": 3,
            "serviceName": "Inactive Service",
            "active": False,
        },
    ],
    "location": {
        "type": "Point",
        "coordinates": [-74.0362, 40.2395],
    },
}


LOCATOR_STORE_RESPONSE = {
    "storeNumber": "1967",
    "address": {
        "addressLine1": "5665 W. Wilshire Blvd.",
        "city": "Los Angeles",
        "state": "CA",
        "zipcode": "90036",
        "country": "USA",
        "phoneNumber": "3237616404",
        "faxNumber": "3236739453",
    },
    "workingHours": [
        {"openTime": "8am", "closeTime": "9pm", "day": "Monday", "index": 1},
        {"openTime": "8am", "closeTime": "9pm", "day": "Tuesday", "index": 2},
        {"openTime": "10am", "closeTime": "6pm", "day": "Sunday", "index": 7},
    ],
    "gmtOffset": -8,
    "latitude": 34.0628,
    "longitude": -118.352,
    "distance": 3.17,
    "placeId": "ChIJJYyMg--5woAReHfejh-9T14",
    "storeStatus": "Open",
    "features": [
        {
            "featureName": "PPS",
            "featureLabel": "Passport Photo Services",
            "featureTooltip": "Passport Photo Services.",
        },
        {
            "featureName": "CPC",
            "featureLabel": "Print & Marketing Services",
            "featureTooltip": "Print & Marketing Services.",
        },
    ],
    "instoreServices": [
        "Print and Marketing Services",
        "Document Printing",
        "Shredding Services",
    ],
}


LOCATOR_API_RESPONSE = {
    "staplesURL": "//www.staples.com",
    "results": {
        "status": "SUCCESS",
        "stores": [LOCATOR_STORE_RESPONSE],
        "count": 1,
    },
}


# ===========================================================================
# TestStaplesStore: Dataclass Tests
# ===========================================================================

class TestStaplesStore:
    """Tests for StaplesStore dataclass."""

    def test_to_dict_full_data(self):
        """Test to_dict with all fields populated."""
        store = StaplesStore(
            store_id="1571",
            name="Staples Ocean Township",
            street_address="1100 State Route 35",
            address_line2="STE A",
            city="Ocean Township",
            state="NJ",
            zip="07712",
            country="US",
            latitude="40.2395",
            longitude="-74.0362",
            phone="(732) 918-9446",
            fax="(732) 517-2393",
            timezone="America/New_York",
            store_url="https://www.staplesconnect.com/nj/ocean-township/1100-state-route-35",
            plaza_mall="Plaza at Ocean",
            store_region="R230",
            store_district="D155",
            store_division="Northeast",
            published_status="ACTIVE",
            hours_monday="8:00 AM - 9:00 PM",
            services="Print and Marketing Services, Shredding Services",
            scraped_at="2026-01-15T12:00:00+00:00",
        )
        result = store.to_dict()
        assert result["store_id"] == "1571"
        assert result["name"] == "Staples Ocean Township"
        assert result["city"] == "Ocean Township"
        assert result["state"] == "NJ"
        assert result["timezone"] == "America/New_York"
        assert result["plaza_mall"] == "Plaza at Ocean"
        assert result["store_region"] == "R230"
        assert result["published_status"] == "ACTIVE"

    def test_to_dict_minimal_data(self):
        """Test to_dict with only required fields."""
        store = StaplesStore(
            store_id="0001",
            name="Staples Store 0001",
            street_address="123 Main St",
        )
        result = store.to_dict()
        assert result["store_id"] == "0001"
        assert result["country"] == "US"
        assert result["city"] == ""
        assert result["scraped_at"] != ""  # Auto-populated

    def test_to_dict_url_field_mapping(self):
        """Test that store_url maps to 'url' key in dict."""
        store = StaplesStore(
            store_id="1571",
            name="Test",
            street_address="123 Main",
            store_url="https://example.com/store/1571",
        )
        result = store.to_dict()
        assert result["url"] == "https://example.com/store/1571"
        assert "store_url" not in result


# ===========================================================================
# TestFormatPhone: Phone number formatting
# ===========================================================================

class TestFormatPhone:
    """Tests for _format_phone helper."""

    def test_ten_digit_phone(self):
        """Standard 10-digit number gets formatted."""
        assert _format_phone("7329189446") == "(732) 918-9446"

    def test_already_formatted(self):
        """Non-10-digit input passes through unchanged."""
        assert _format_phone("(732) 918-9446") == "(732) 918-9446"

    def test_empty_string(self):
        """Empty string returns empty."""
        assert _format_phone("") == ""

    def test_short_number(self):
        """Short number passes through."""
        assert _format_phone("12345") == "12345"

    def test_number_with_dashes(self):
        """Digits extracted from dashed format."""
        assert _format_phone("732-918-9446") == "(732) 918-9446"


# ===========================================================================
# TestFormatHoursStaplesConnect: Hours parsing
# ===========================================================================

class TestFormatHoursStaplesConnect:
    """Tests for _format_hours_staplesconnect."""

    def test_normal_hours(self):
        """Parse standard store hours."""
        hours = [
            {
                "open24Hr": False,
                "close24Hr": False,
                "open": "08:00 AM",
                "close": "09:00 PM",
                "formattedStoreHours": "8:00 AM - 9:00 PM",
                "dayShort": "MON",
                "day": "MONDAY",
            },
        ]
        result = _format_hours_staplesconnect(hours)
        assert result["monday"] == "8:00 AM - 9:00 PM"

    def test_closed_day(self):
        """Closed day returns 'Closed'."""
        hours = [{"close24Hr": True, "dayShort": "SUN"}]
        result = _format_hours_staplesconnect(hours)
        assert result["sunday"] == "Closed"

    def test_24_hour_day(self):
        """Open 24 hours returns correct string."""
        hours = [{"open24Hr": True, "close24Hr": False, "dayShort": "MON"}]
        result = _format_hours_staplesconnect(hours)
        assert result["monday"] == "Open 24 Hours"

    def test_fallback_to_open_close(self):
        """Falls back to open/close when formattedStoreHours is empty."""
        hours = [
            {
                "open24Hr": False,
                "close24Hr": False,
                "open": "9:00 AM",
                "close": "8:00 PM",
                "formattedStoreHours": "",
                "dayShort": "TUE",
            },
        ]
        result = _format_hours_staplesconnect(hours)
        assert result["tuesday"] == "9:00 AM - 8:00 PM"

    def test_empty_hours(self):
        """Empty list returns empty dict."""
        assert _format_hours_staplesconnect([]) == {}

    def test_unknown_day_short(self):
        """Unknown dayShort is skipped."""
        hours = [{"dayShort": "XYZ", "formattedStoreHours": "test"}]
        result = _format_hours_staplesconnect(hours)
        assert result == {}


# ===========================================================================
# TestFormatHoursLocator: Store locator hours parsing
# ===========================================================================

class TestFormatHoursLocator:
    """Tests for _format_hours_locator."""

    def test_normal_hours(self):
        """Parse store locator working hours."""
        hours = [
            {"openTime": "8am", "closeTime": "9pm", "day": "Monday", "index": 1},
        ]
        result = _format_hours_locator(hours)
        assert result["monday"] == "8am - 9pm"

    def test_case_insensitive_day(self):
        """Day names are case-insensitive."""
        hours = [
            {"openTime": "10am", "closeTime": "6pm", "day": "SUNDAY", "index": 7},
        ]
        result = _format_hours_locator(hours)
        assert result["sunday"] == "10am - 6pm"

    def test_invalid_day_skipped(self):
        """Invalid day names are skipped."""
        hours = [{"openTime": "8am", "closeTime": "9pm", "day": "Funday"}]
        result = _format_hours_locator(hours)
        assert result == {}

    def test_missing_times_skipped(self):
        """Entries without times are skipped."""
        hours = [{"day": "Monday"}]
        result = _format_hours_locator(hours)
        assert result == {}


# ===========================================================================
# TestFormatFeatures: Feature formatting
# ===========================================================================

class TestFormatFeatures:
    """Tests for _format_features."""

    def test_multiple_features(self):
        """Multiple features joined with commas."""
        features = [
            {"featureName": "PPS", "featureLabel": "Passport Photo Services"},
            {"featureName": "CPC", "featureLabel": "Print & Marketing Services"},
        ]
        result = _format_features(features)
        assert "Passport Photo Services" in result
        assert "Print & Marketing Services" in result
        assert ", " in result

    def test_empty_features(self):
        """Empty list returns empty string."""
        assert _format_features([]) == ""

    def test_feature_without_label(self):
        """Features without featureLabel are skipped."""
        features = [{"featureName": "PPS"}]
        assert _format_features(features) == ""


# ===========================================================================
# TestFormatServices: Service formatting
# ===========================================================================

class TestFormatServices:
    """Tests for _format_services."""

    def test_string_list(self):
        """String list (from locator) joins to comma-separated."""
        services = ["Print and Marketing Services", "Shredding Services"]
        result = _format_services(services)
        assert result == "Print and Marketing Services, Shredding Services"

    def test_dict_list_active_only(self):
        """Dict list (from StaplesConnect) filters by active flag."""
        services = [
            {"serviceName": "Print", "active": True},
            {"serviceName": "Inactive", "active": False},
            {"serviceName": "Shredding", "active": True},
        ]
        result = _format_services(services)
        assert "Print" in result
        assert "Shredding" in result
        assert "Inactive" not in result

    def test_empty_list(self):
        """Empty list returns empty string."""
        assert _format_services([]) == ""

    def test_none_input(self):
        """None input returns empty string."""
        assert _format_services(None) == ""


# ===========================================================================
# TestParseStaplesConnectStore: Full store parsing
# ===========================================================================

class TestParseStaplesConnectStore:
    """Tests for _parse_staplesconnect_store."""

    def test_full_response(self):
        """Parse complete StaplesConnect response."""
        store = _parse_staplesconnect_store(STAPLESCONNECT_STORE_RESPONSE)
        assert store is not None
        assert store.store_id == "1571"
        assert store.name == "Staples Retail Store 1571 - Ocean Township NJ"
        assert store.street_address == "1100 State Route 35"
        assert store.address_line2 == "STE A"
        assert store.city == "Ocean Township"
        assert store.state == "NJ"
        assert store.zip == "07712"
        assert store.latitude == "40.2395"
        assert store.longitude == "-74.0362"
        assert store.timezone == "America/New_York"
        assert store.plaza_mall == "Plaza at Ocean"
        assert store.store_region == "R230"
        assert store.store_district == "D155"
        assert store.store_division == "Northeast"
        assert store.published_status == "ACTIVE"

    def test_hours_parsed(self):
        """Hours are parsed into per-day fields."""
        store = _parse_staplesconnect_store(STAPLESCONNECT_STORE_RESPONSE)
        assert store.hours_monday == "8:00 AM - 9:00 PM"
        assert store.hours_tuesday == "8:00 AM - 9:00 PM"
        assert store.hours_sunday == "Closed"

    def test_services_parsed(self):
        """Active services parsed, inactive filtered."""
        store = _parse_staplesconnect_store(STAPLESCONNECT_STORE_RESPONSE)
        assert "Print and Marketing Services" in store.services
        assert "Shredding Services" in store.services
        assert "Inactive Service" not in store.services

    def test_store_url_built(self):
        """Store URL constructed from address slugs."""
        store = _parse_staplesconnect_store(STAPLESCONNECT_STORE_RESPONSE)
        assert store.store_url == "https://www.staplesconnect.com/nj/ocean-township/1100-state-route-35"

    def test_phone_formatted(self):
        """Phone number formatted correctly."""
        store = _parse_staplesconnect_store(STAPLESCONNECT_STORE_RESPONSE)
        assert store.phone == "(732) 918-9446"

    def test_missing_store_number(self):
        """Returns None if storeNumber is missing."""
        data = {"name": "Test Store"}
        assert _parse_staplesconnect_store(data) is None

    def test_empty_data(self):
        """Returns None for empty dict."""
        assert _parse_staplesconnect_store({}) is None

    def test_fallback_to_store_title(self):
        """Falls back to storeTitle if name is missing."""
        data = {
            "storeNumber": "9999",
            "storeTitle": "Staples Test Store",
            "address": {},
        }
        store = _parse_staplesconnect_store(data)
        assert store.name == "Staples Test Store"


# ===========================================================================
# TestParseLocatorStore: Store locator parsing
# ===========================================================================

class TestParseLocatorStore:
    """Tests for _parse_locator_store."""

    def test_full_response(self):
        """Parse complete store locator response."""
        store = _parse_locator_store(LOCATOR_STORE_RESPONSE)
        assert store is not None
        assert store.store_id == "1967"
        assert store.street_address == "5665 W. Wilshire Blvd."
        assert store.city == "Los Angeles"
        assert store.state == "CA"
        assert store.zip == "90036"
        assert store.latitude == "34.0628"
        assert store.longitude == "-118.352"
        assert store.google_place_id == "ChIJJYyMg--5woAReHfejh-9T14"

    def test_features_parsed(self):
        """Features parsed to comma-separated string."""
        store = _parse_locator_store(LOCATOR_STORE_RESPONSE)
        assert "Passport Photo Services" in store.features
        assert "Print & Marketing Services" in store.features

    def test_services_parsed(self):
        """In-store services parsed."""
        store = _parse_locator_store(LOCATOR_STORE_RESPONSE)
        assert "Print and Marketing Services" in store.services
        assert "Document Printing" in store.services

    def test_hours_parsed(self):
        """Working hours parsed."""
        store = _parse_locator_store(LOCATOR_STORE_RESPONSE)
        assert store.hours_monday == "8am - 9pm"
        assert store.hours_sunday == "10am - 6pm"

    def test_missing_store_number(self):
        """Returns None if storeNumber missing."""
        assert _parse_locator_store({"address": {}}) is None


# ===========================================================================
# TestMergeStoreData: Data merging logic
# ===========================================================================

class TestMergeStoreData:
    """Tests for _merge_store_data."""

    def test_secondary_fills_features(self):
        """Secondary's features fill primary's empty features."""
        primary = StaplesStore(store_id="1571", name="Test", street_address="123 Main")
        secondary = StaplesStore(
            store_id="1571", name="Test", street_address="123 Main",
            features="Passport Photo, Print Services",
        )
        merged = _merge_store_data(primary, secondary)
        assert merged.features == "Passport Photo, Print Services"

    def test_primary_features_preserved(self):
        """Primary features are not overwritten."""
        primary = StaplesStore(
            store_id="1571", name="Test", street_address="123 Main",
            features="Original Features",
        )
        secondary = StaplesStore(
            store_id="1571", name="Test", street_address="123 Main",
            features="Secondary Features",
        )
        merged = _merge_store_data(primary, secondary)
        assert merged.features == "Original Features"

    def test_google_place_id_merged(self):
        """Google Place ID merged from secondary."""
        primary = StaplesStore(store_id="1571", name="Test", street_address="123 Main")
        secondary = StaplesStore(
            store_id="1571", name="Test", street_address="123 Main",
            google_place_id="ChIJ...",
        )
        merged = _merge_store_data(primary, secondary)
        assert merged.google_place_id == "ChIJ..."

    def test_services_combined(self):
        """Services from both sources combined and deduplicated."""
        primary = StaplesStore(
            store_id="1571", name="Test", street_address="123 Main",
            services="Print, Shredding",
        )
        secondary = StaplesStore(
            store_id="1571", name="Test", street_address="123 Main",
            services="Shredding, Amazon Returns",
        )
        merged = _merge_store_data(primary, secondary)
        assert "Print" in merged.services
        assert "Shredding" in merged.services
        assert "Amazon Returns" in merged.services

    def test_coordinates_filled(self):
        """Empty coordinates filled from secondary."""
        primary = StaplesStore(store_id="1571", name="Test", street_address="123 Main")
        secondary = StaplesStore(
            store_id="1571", name="Test", street_address="123 Main",
            latitude="40.2", longitude="-74.0",
        )
        merged = _merge_store_data(primary, secondary)
        assert merged.latitude == "40.2"
        assert merged.longitude == "-74.0"


# ===========================================================================
# TestGenerateStoreNumbers: Store number generation
# ===========================================================================

class TestGenerateStoreNumbers:
    """Tests for _generate_store_numbers."""

    def test_generates_correct_count(self):
        """Generates correct number of store numbers from configured ranges."""
        numbers = _generate_store_numbers()
        # Range (1, 2001) = 2000 numbers, (5001, 5500) = 499 numbers
        assert len(numbers) == 2499

    def test_zero_padded(self):
        """Store numbers are zero-padded to 4 digits."""
        numbers = _generate_store_numbers()
        assert numbers[0] == "0001"
        assert numbers[1] == "0002"
        assert "0001" in numbers

    def test_includes_outlier_range(self):
        """Includes outlier range (5001+)."""
        numbers = _generate_store_numbers()
        assert "5001" in numbers
        assert "5499" in numbers

    def test_excludes_boundaries(self):
        """Excludes upper boundaries."""
        numbers = _generate_store_numbers()
        assert "2001" not in numbers
        assert "5500" not in numbers


# ===========================================================================
# TestScanStoreNumbers: Phase 1 (mocked)
# ===========================================================================

class TestScanStoreNumbers:
    """Tests for _scan_store_numbers with mocked proxy client."""

    @patch("src.scrapers.staples._scan_worker")
    def test_basic_scan(self, mock_worker):
        """Basic scan finds stores from valid numbers."""
        valid_store = StaplesStore(
            store_id="0001", name="Staples Brighton", street_address="123 Main",
        )
        # Return valid store for 0001, None for others
        mock_worker.side_effect = lambda num, _: (
            (num, valid_store) if num == "0001" else (num, None)
        )

        mock_proxy = MagicMock()
        retailer_config = {"parallel_workers": 1, "checkpoint_interval": 999}

        stores, checkpoints_used = _scan_store_numbers(
            proxy_client=mock_proxy,
            retailer_config=retailer_config,
            test=True,  # Only scan first 20
        )
        assert not checkpoints_used

    @patch("src.scrapers.staples._generate_store_numbers")
    @patch("src.scrapers.staples._scan_worker")
    def test_test_mode_limits_numbers(self, mock_worker, mock_generate):
        """Test mode scans only first 20 numbers."""
        mock_generate.return_value = [str(i).zfill(4) for i in range(1, 100)]
        mock_worker.return_value = ("0001", None)

        mock_proxy = MagicMock()
        retailer_config = {"parallel_workers": 1, "checkpoint_interval": 999}

        _scan_store_numbers(
            proxy_client=mock_proxy,
            retailer_config=retailer_config,
            test=True,
        )
        # In test mode, only first 20 should be submitted
        assert mock_worker.call_count <= 20


# ===========================================================================
# TestZipCodeGapFill: Phase 2 (mocked)
# ===========================================================================

class TestZipCodeGapFill:
    """Tests for _zip_code_gap_fill with mocked search."""

    @patch("src.scrapers.staples._search_stores_by_zip")
    def test_finds_new_stores(self, mock_search):
        """Gap-fill discovers stores not in Phase 1 results."""
        new_store = StaplesStore(
            store_id="9999", name="New Store", street_address="999 Oak",
        )
        mock_search.return_value = [new_store]

        mock_proxy = MagicMock()
        known_ids = {"0001", "0002"}

        result = _zip_code_gap_fill(mock_proxy, known_ids, test=True)
        assert "9999" in result

    @patch("src.scrapers.staples._search_stores_by_zip")
    def test_skips_known_stores(self, mock_search):
        """Gap-fill doesn't duplicate stores from Phase 1."""
        known_store = StaplesStore(
            store_id="0001", name="Known Store", street_address="123 Main",
        )
        mock_search.return_value = [known_store]

        mock_proxy = MagicMock()
        known_ids = {"0001"}

        result = _zip_code_gap_fill(mock_proxy, known_ids, test=True)
        assert "0001" not in result

    @patch("src.scrapers.staples._search_stores_by_zip")
    def test_test_mode_limits_zips(self, mock_search):
        """Test mode only sweeps 5 ZIP codes."""
        mock_search.return_value = []

        mock_proxy = MagicMock()
        _zip_code_gap_fill(mock_proxy, set(), test=True)
        assert mock_search.call_count == 5


# ===========================================================================
# TestEnrichServices: Phase 3 (mocked)
# ===========================================================================

class TestEnrichServices:
    """Tests for _enrich_services with mocked API calls."""

    @patch("src.scrapers.staples._fetch_store_services")
    def test_enriches_services(self, mock_fetch):
        """Service enrichment updates store services field."""
        mock_fetch.return_value = [
            {"serviceName": "Tech Services", "active": True},
            {"serviceName": "Print Services", "active": True},
        ]

        stores = {
            "1571": StaplesStore(
                store_id="1571", name="Test", street_address="123 Main",
            ),
        }

        mock_proxy = MagicMock()
        _enrich_services(stores, mock_proxy, max_workers=1, test=True)

        assert "Tech Services" in stores["1571"].services

    @patch("src.scrapers.staples._fetch_store_services")
    def test_handles_errors_gracefully(self, mock_fetch):
        """Service enrichment handles API errors gracefully."""
        mock_fetch.side_effect = Exception("API error")

        stores = {
            "1571": StaplesStore(
                store_id="1571", name="Test", street_address="123 Main",
                services="Existing",
            ),
        }

        mock_proxy = MagicMock()
        _enrich_services(stores, mock_proxy, max_workers=1, test=True)

        # Original services preserved
        assert stores["1571"].services == "Existing"


# ===========================================================================
# TestRunFunction: Integration test (all phases mocked)
# ===========================================================================

class TestRunFunction:
    """Tests for the main run() entry point."""

    @patch("src.scrapers.staples._enrich_services")
    @patch("src.scrapers.staples._zip_code_gap_fill")
    @patch("src.scrapers.staples._scan_store_numbers")
    @patch("src.scrapers.staples.ProxyClient")
    def test_run_returns_standard_format(
        self, mock_proxy_cls, mock_scan, mock_gap_fill, mock_enrich
    ):
        """run() returns dict with stores, count, checkpoints_used."""
        store = StaplesStore(
            store_id="1571",
            name="Staples Ocean Township",
            street_address="1100 State Route 35",
            city="Ocean Township",
            state="NJ",
            zip="07712",
        )
        mock_scan.return_value = ({"1571": store}, False)
        mock_gap_fill.return_value = {}
        mock_enrich.return_value = None

        mock_session = MagicMock()
        retailer_config = {
            "proxy": {"mode": "direct"},
            "parallel_workers": 1,
        }

        result = run(mock_session, retailer_config, "staples", test=True)

        assert "stores" in result
        assert "count" in result
        assert "checkpoints_used" in result
        assert result["count"] == 1
        assert result["stores"][0]["store_id"] == "1571"

    @patch("src.scrapers.staples._enrich_services")
    @patch("src.scrapers.staples._zip_code_gap_fill")
    @patch("src.scrapers.staples._scan_store_numbers")
    @patch("src.scrapers.staples.ProxyClient")
    def test_run_merges_gap_fill(
        self, mock_proxy_cls, mock_scan, mock_gap_fill, mock_enrich
    ):
        """run() merges gap-fill stores with scan results."""
        scan_store = StaplesStore(
            store_id="1571", name="Scan Store", street_address="123 Main",
            city="Town", state="NJ", zip="07712",
        )
        gap_store = StaplesStore(
            store_id="9999", name="Gap Store", street_address="999 Oak",
            city="City", state="CA", zip="90001",
        )
        mock_scan.return_value = ({"1571": scan_store}, False)
        mock_gap_fill.return_value = {"9999": gap_store}
        mock_enrich.return_value = None

        result = run(MagicMock(), {"proxy": {"mode": "direct"}, "parallel_workers": 1}, test=True)

        assert result["count"] == 2
        store_ids = [s["store_id"] for s in result["stores"]]
        assert "1571" in store_ids
        assert "9999" in store_ids

    @patch("src.scrapers.staples._enrich_services")
    @patch("src.scrapers.staples._zip_code_gap_fill")
    @patch("src.scrapers.staples._scan_store_numbers")
    @patch("src.scrapers.staples.ProxyClient")
    def test_run_empty_results(
        self, mock_proxy_cls, mock_scan, mock_gap_fill, mock_enrich
    ):
        """run() handles zero stores gracefully."""
        mock_scan.return_value = ({}, False)
        mock_gap_fill.return_value = {}
        mock_enrich.return_value = None

        result = run(MagicMock(), {"proxy": {"mode": "direct"}, "parallel_workers": 1}, test=True)

        assert result["count"] == 0
        assert result["stores"] == []
        assert result["checkpoints_used"] is False

    @patch("src.scrapers.staples._enrich_services")
    @patch("src.scrapers.staples._zip_code_gap_fill")
    @patch("src.scrapers.staples._scan_store_numbers")
    @patch("src.scrapers.staples.ProxyClient")
    def test_run_merges_duplicate_from_gap_fill(
        self, mock_proxy_cls, mock_scan, mock_gap_fill, mock_enrich
    ):
        """run() merges gap-fill data when store ID already exists."""
        scan_store = StaplesStore(
            store_id="1571", name="Scan Store", street_address="123 Main",
            city="Town", state="NJ", zip="07712",
        )
        gap_store = StaplesStore(
            store_id="1571", name="Gap Store", street_address="123 Main",
            features="Passport Photo, Print Services",
            google_place_id="ChIJ...",
        )
        mock_scan.return_value = ({"1571": scan_store}, False)
        mock_gap_fill.return_value = {"1571": gap_store}
        mock_enrich.return_value = None

        result = run(MagicMock(), {"proxy": {"mode": "direct"}, "parallel_workers": 1}, test=True)

        assert result["count"] == 1
        assert "Passport Photo" in result["stores"][0]["features"]
        assert result["stores"][0]["google_place_id"] == "ChIJ..."


# ===========================================================================
# TestConfig: Configuration module
# ===========================================================================

class TestConfig:
    """Tests for staples_config module."""

    def test_build_store_detail_url(self):
        """build_store_detail_url constructs correct URL."""
        url = config.build_store_detail_url("1571")
        assert url == "https://www.staplesconnect.com/api/store/1571"

    def test_build_services_url(self):
        """build_services_url constructs correct URL."""
        url = config.build_services_url("1571")
        assert "getStoreServicesByStoreNumber/1571" in url

    def test_get_headers_returns_dict(self):
        """get_headers returns a dict with required keys."""
        headers = config.get_headers()
        assert "User-Agent" in headers
        assert "Accept" in headers

    def test_get_locator_headers(self):
        """get_locator_headers includes Content-Type."""
        headers = config.get_locator_headers()
        assert headers["Content-Type"] == "application/json"
        assert "Referer" in headers

    def test_store_number_ranges(self):
        """STORE_NUMBER_RANGES has expected structure."""
        assert len(config.STORE_NUMBER_RANGES) >= 2
        assert config.STORE_NUMBER_RANGES[0] == (1, 2001)

    def test_gap_fill_zip_codes(self):
        """GAP_FILL_ZIP_CODES has reasonable coverage."""
        assert len(config.GAP_FILL_ZIP_CODES) >= 50
        assert "10001" in config.GAP_FILL_ZIP_CODES
        assert "90001" in config.GAP_FILL_ZIP_CODES
