"""Unit tests for GameStop scraper."""
# pylint: disable=no-member

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.scrapers.gamestop import (
    GameStopStore,
    _parse_hours,
    _parse_store_from_api,
    _extract_store_urls_from_html,
    fetch_stores_at_point,
    discover_all_stores,
    extract_jsonld_from_page,
    enrich_store,
    enrich_all_stores,
    run,
    reset_request_counter,
)
from config import gamestop_config


# =============================================================================
# Sample Data Fixtures
# =============================================================================

SAMPLE_API_STORE = {
    "ID": "6562",
    "name": "East 14th Street New York",
    "address1": "32 E 14th ST",
    "address2": None,
    "city": "New York",
    "postalCode": "10003",
    "latitude": 40.73530294,
    "longitude": -73.99191706,
    "phone": "(212) 242-2567",
    "stateCode": "NY",
    "countryCode": {},
    "storeHours": "refer to custom attribute, storeOperationHours",
    "storeOperationHours": json.dumps([
        {"day": "Sun", "open": "1000", "close": "2000"},
        {"day": "Mon", "open": "1000", "close": "2100"},
        {"day": "Tue", "open": "1000", "close": "2100"},
    ]),
    "storeBrand": {},
    "storeMode": "ACTIVE",
    "storeMiddleDayClosure": False,
    "isPreferredStore": False,
    "brandIcon": "store-detail-gamestop",
    "distance": "0.94",
}

SAMPLE_API_RESPONSE = {
    "action": "Stores-FindStores",
    "queryString": "postalCode=10001&radius=15",
    "locale": "default",
    "stores": [SAMPLE_API_STORE],
    "storesResultsHtml": (
        '<div class="store-result">'
        '<a href="/store/us/ny/new-york/6562/east-14th-street-new-york-gamestop">'
        "East 14th Street</a></div>"
    ),
    "radius": 15,
}

SAMPLE_JSONLD = {
    "@context": "https://schema.org",
    "@type": "Store",
    "name": "East 14th Street New York",
    "alternateName": "GameStop",
    "description": "Visit East 14th Street New York in New York, NY...",
    "url": "https://www.gamestop.com/store/us/ny/new-york/6562/east-14th-street-new-york-gamestop",
    "image": "https://media.gamestop.com/i/gamestop/aff_gme_storefront",
    "knowsAbout": ["Video Games", "Gaming Consoles", "PS5", "Nintendo Switch"],
    "address": {
        "@type": "PostalAddress",
        "streetAddress": "32 E 14th ST",
        "addressLocality": "New York",
        "addressRegion": "NY",
        "postalCode": "10003",
    },
    "openingHours": ["Su 10:00-20:00", "Mo 10:00-21:00"],
    "telephone": "(212) 242-2567",
    "currenciesAccepted": "USD",
    "paymentAccepted": ["Cash", "Credit Card", "Personal Checks"],
}

SAMPLE_DETAIL_HTML = """
<html><head><title>GameStop Store</title></head>
<body>
<script type="application/ld+json">
{jsonld}
</script>
<div class="store-content">Store details here</div>
</body></html>
""".format(jsonld=json.dumps(SAMPLE_JSONLD))


# =============================================================================
# GameStopStore Dataclass Tests
# =============================================================================


class TestGameStopStore:
    """Tests for GameStopStore dataclass."""

    def test_to_dict_contains_all_fields(self):
        """Test dictionary conversion contains all expected fields."""
        store = GameStopStore(
            store_id="6562",
            name="East 14th Street New York",
            street_address="32 E 14th ST",
            address2="",
            city="New York",
            state="NY",
            zip_code="10003",
            country="US",
            latitude=40.73530294,
            longitude=-73.99191706,
            phone="(212) 242-2567",
            store_mode="ACTIVE",
            hours='[{"day": "Mon", "open": "1000", "close": "2100"}]',
            midday_closure=False,
            description="Visit this store",
            knows_about="Video Games|PS5",
            payment_accepted="Cash|Credit Card",
            currencies_accepted="USD",
            image_url="https://example.com/image.jpg",
            url="https://www.gamestop.com/store/us/ny/new-york/6562/test",
            scraped_at="2026-02-06T12:00:00",
        )
        result = store.to_dict()

        assert result["store_id"] == "6562"
        assert result["name"] == "East 14th Street New York"
        assert result["street_address"] == "32 E 14th ST"
        assert result["city"] == "New York"
        assert result["state"] == "NY"
        assert result["zip_code"] == "10003"
        assert result["latitude"] == "40.73530294"
        assert result["longitude"] == "-73.99191706"
        assert result["phone"] == "(212) 242-2567"
        assert result["store_mode"] == "ACTIVE"
        assert result["midday_closure"] is False
        assert result["knows_about"] == "Video Games|PS5"
        assert result["payment_accepted"] == "Cash|Credit Card"
        assert result["currencies_accepted"] == "USD"

    def test_to_dict_none_coordinates(self):
        """Test coordinates are empty string when None."""
        store = GameStopStore(
            store_id="1000", name="Test", street_address="123", address2="",
            city="City", state="TX", zip_code="75001", country="US",
            latitude=None, longitude=None, phone="", store_mode="ACTIVE",
            hours=None, midday_closure=False, description="", knows_about="",
            payment_accepted="", currencies_accepted="", image_url="",
            url="", scraped_at="",
        )
        result = store.to_dict()
        assert result["latitude"] == ""
        assert result["longitude"] == ""

    def test_to_dict_with_coordinates(self):
        """Test coordinates are converted to strings."""
        store = GameStopStore(
            store_id="1000", name="Test", street_address="123", address2="",
            city="City", state="TX", zip_code="75001", country="US",
            latitude=30.123, longitude=-95.456, phone="", store_mode="ACTIVE",
            hours=None, midday_closure=False, description="", knows_about="",
            payment_accepted="", currencies_accepted="", image_url="",
            url="", scraped_at="",
        )
        result = store.to_dict()
        assert result["latitude"] == "30.123"
        assert result["longitude"] == "-95.456"


# =============================================================================
# Hours Parsing Tests
# =============================================================================


class TestParseHours:
    """Tests for _parse_hours function."""

    def test_valid_hours(self):
        """Test parsing valid double-encoded hours."""
        hours_str = json.dumps([
            {"day": "Sun", "open": "1000", "close": "2000"},
            {"day": "Mon", "open": "1000", "close": "2100"},
        ])
        result = _parse_hours(hours_str)
        parsed = json.loads(result)

        assert len(parsed) == 2
        assert parsed[0]["day"] == "Sun"
        assert parsed[0]["open"] == "1000"
        assert parsed[0]["close"] == "2000"
        assert parsed[1]["day"] == "Mon"

    def test_empty_string_returns_none(self):
        """Test empty string returns None."""
        assert _parse_hours("") is None

    def test_none_returns_none(self):
        """Test None input returns None."""
        assert _parse_hours(None) is None

    def test_invalid_json_returns_none(self):
        """Test invalid JSON returns None."""
        assert _parse_hours("not json {[") is None

    def test_non_list_json_returns_none(self):
        """Test non-list JSON returns None."""
        assert _parse_hours('"just a string"') is None

    def test_non_dict_entries_skipped(self):
        """Test non-dict entries in array are skipped."""
        hours_str = json.dumps(["not a dict", 42])
        result = _parse_hours(hours_str)
        assert result is None

    def test_missing_fields_use_defaults(self):
        """Test entries with missing fields use empty string defaults."""
        hours_str = json.dumps([{"day": "Mon"}])
        result = _parse_hours(hours_str)
        parsed = json.loads(result)

        assert parsed[0]["day"] == "Mon"
        assert parsed[0]["open"] == ""
        assert parsed[0]["close"] == ""


# =============================================================================
# API Store Parsing Tests
# =============================================================================


class TestParseStoreFromApi:
    """Tests for _parse_store_from_api function."""

    def test_valid_store(self):
        """Test parsing a complete API store response."""
        store = _parse_store_from_api(SAMPLE_API_STORE)

        assert store is not None
        assert store.store_id == "6562"
        assert store.name == "East 14th Street New York"
        assert store.street_address == "32 E 14th ST"
        assert store.address2 == ""  # None -> ""
        assert store.city == "New York"
        assert store.state == "NY"
        assert store.zip_code == "10003"
        assert store.country == "US"
        assert store.latitude == 40.73530294
        assert store.longitude == -73.99191706
        assert store.phone == "(212) 242-2567"
        assert store.store_mode == "ACTIVE"
        assert store.midday_closure is False

    def test_hours_parsed(self):
        """Test that double-encoded hours are parsed."""
        store = _parse_store_from_api(SAMPLE_API_STORE)
        assert store is not None
        assert store.hours is not None

        parsed = json.loads(store.hours)
        assert len(parsed) == 3
        assert parsed[0]["day"] == "Sun"

    def test_missing_id_returns_none(self):
        """Test returns None when ID is missing."""
        raw = {"name": "Test Store", "city": "NYC"}
        assert _parse_store_from_api(raw) is None

    def test_missing_name_returns_none(self):
        """Test returns None when name is missing."""
        raw = {"ID": "6562", "city": "NYC"}
        assert _parse_store_from_api(raw) is None

    def test_empty_name_returns_none(self):
        """Test returns None when name is empty string."""
        raw = {"ID": "6562", "name": "  ", "city": "NYC"}
        assert _parse_store_from_api(raw) is None

    def test_detail_url_constructed(self):
        """Test store detail URL is built from store data."""
        store = _parse_store_from_api(SAMPLE_API_STORE)
        assert store is not None
        assert "/store/us/ny/" in store.url
        assert "/6562/" in store.url
        assert store.url.endswith("-gamestop")

    def test_missing_optional_fields(self):
        """Test handles missing optional fields gracefully."""
        raw = {
            "ID": "1000",
            "name": "Minimal Store",
        }
        store = _parse_store_from_api(raw)
        assert store is not None
        assert store.street_address == ""
        assert store.phone == ""
        assert store.store_mode == ""
        assert store.hours is None
        assert store.midday_closure is False

    def test_null_address2_becomes_empty(self):
        """Test null address2 is converted to empty string."""
        raw = {"ID": "1000", "name": "Test", "address2": None}
        store = _parse_store_from_api(raw)
        assert store is not None
        assert store.address2 == ""

    def test_integer_id_normalized_to_string(self):
        """Test integer IDs from SFCC API are normalized to strings."""
        raw = {"ID": 6562, "name": "Test Store", "stateCode": "NY", "city": "NYC"}
        store = _parse_store_from_api(raw)
        assert store is not None
        assert store.store_id == "6562"
        assert isinstance(store.store_id, str)


# =============================================================================
# Store URL Extraction Tests
# =============================================================================


class TestExtractStoreUrlsFromHtml:
    """Tests for _extract_store_urls_from_html function."""

    def test_extracts_valid_urls(self):
        """Test extraction of store URLs from results HTML."""
        html = (
            '<a href="/store/us/ny/new-york/6562/east-14th-street-gamestop">'
            '<a href="/store/us/ca/los-angeles/4321/la-store-gamestop">'
        )
        urls = _extract_store_urls_from_html(html)

        assert "6562" in urls
        assert "4321" in urls
        assert "gamestop.com" in urls["6562"]

    def test_empty_html_returns_empty(self):
        """Test empty HTML returns empty dict."""
        assert _extract_store_urls_from_html("") == {}

    def test_none_returns_empty(self):
        """Test None returns empty dict."""
        assert _extract_store_urls_from_html(None) == {}

    def test_no_matching_urls_returns_empty(self):
        """Test HTML without store URLs returns empty dict."""
        html = '<a href="/products/game">Product</a>'
        assert _extract_store_urls_from_html(html) == {}

    def test_non_numeric_store_id_skipped(self):
        """Test URLs with non-numeric store IDs are skipped."""
        html = '<a href="/store/us/ny/nyc/abc/test-gamestop">'
        urls = _extract_store_urls_from_html(html)
        assert len(urls) == 0


# =============================================================================
# API Fetch Tests
# =============================================================================


class TestFetchStoresAtPoint:
    """Tests for fetch_stores_at_point function."""

    def setup_method(self):
        """Reset request counter before each test."""
        reset_request_counter()

    @patch("src.scrapers.gamestop.check_pause_logic")
    @patch("src.scrapers.gamestop.utils.get_with_retry")
    def test_successful_fetch(self, mock_get, mock_pause):
        """Test successful API fetch returns stores."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_API_RESPONSE
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response

        result = fetch_stores_at_point(Mock(), 40.7, -74.0)

        assert len(result) == 1
        assert result[0]["ID"] == "6562"

    @patch("src.scrapers.gamestop.utils.get_with_retry")
    def test_failed_request_returns_empty(self, mock_get):
        """Test failed request returns empty list."""
        mock_get.return_value = None
        result = fetch_stores_at_point(Mock(), 40.7, -74.0)
        assert result == []

    @patch("src.scrapers.gamestop.check_pause_logic")
    @patch("src.scrapers.gamestop.utils.get_with_retry")
    def test_non_json_response_returns_empty(self, mock_get, mock_pause):
        """Test Cloudflare challenge page (non-JSON) returns empty."""
        mock_response = Mock()
        mock_response.headers = {"Content-Type": "text/html"}
        mock_get.return_value = mock_response

        result = fetch_stores_at_point(Mock(), 40.7, -74.0)
        assert result == []

    @patch("src.scrapers.gamestop.check_pause_logic")
    @patch("src.scrapers.gamestop.utils.get_with_retry")
    def test_json_parse_error_returns_empty(self, mock_get, mock_pause):
        """Test malformed JSON returns empty list."""
        mock_response = Mock()
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.side_effect = json.JSONDecodeError("err", "", 0)
        mock_get.return_value = mock_response

        result = fetch_stores_at_point(Mock(), 40.7, -74.0)
        assert result == []

    @patch("src.scrapers.gamestop.check_pause_logic")
    @patch("src.scrapers.gamestop.utils.get_with_retry")
    def test_resolved_urls_attached(self, mock_get, mock_pause):
        """Test store URLs from HTML are attached to store dicts."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_API_RESPONSE
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response

        result = fetch_stores_at_point(Mock(), 40.7, -74.0)

        assert result[0].get("_resolved_url") is not None
        assert "6562" in result[0]["_resolved_url"]


# =============================================================================
# Grid Discovery Tests
# =============================================================================


class TestDiscoverAllStores:
    """Tests for discover_all_stores function."""

    def setup_method(self):
        """Reset request counter before each test."""
        reset_request_counter()

    @patch("src.scrapers.gamestop.utils.random_delay")
    @patch("src.scrapers.gamestop.utils.select_delays")
    @patch("src.scrapers.gamestop.fetch_stores_at_point")
    @patch("src.scrapers.gamestop.config.generate_us_grid")
    def test_discovers_and_deduplicates(
        self, mock_grid, mock_fetch, mock_delays, mock_delay
    ):
        """Test grid search discovers and deduplicates stores."""
        mock_grid.return_value = [(40.0, -74.0), (41.0, -73.0)]
        mock_delays.return_value = (0.1, 0.2)

        # Both grid points return the same store + one unique each
        store1 = {"ID": "6562", "name": "Store A", "stateCode": "NY",
                   "city": "NYC", "storeOperationHours": ""}
        store2 = {"ID": "7777", "name": "Store B", "stateCode": "NJ",
                   "city": "Newark", "storeOperationHours": ""}
        mock_fetch.side_effect = [
            [store1, store2],
            [store1],  # duplicate
        ]

        yaml_config = {"proxy": {"mode": "direct"}}
        result = discover_all_stores(Mock(), "gamestop", yaml_config)

        assert len(result) == 2
        assert "6562" in result
        assert "7777" in result

    @patch("src.scrapers.gamestop.utils.random_delay")
    @patch("src.scrapers.gamestop.utils.select_delays")
    @patch("src.scrapers.gamestop.fetch_stores_at_point")
    @patch("src.scrapers.gamestop.config.generate_us_grid")
    def test_empty_grid_returns_empty(
        self, mock_grid, mock_fetch, mock_delays, mock_delay
    ):
        """Test empty grid produces no stores."""
        mock_grid.return_value = []
        mock_delays.return_value = (0.1, 0.2)

        result = discover_all_stores(Mock(), "gamestop", {})
        assert len(result) == 0


# =============================================================================
# JSON-LD Extraction Tests
# =============================================================================


class TestExtractJsonldFromPage:
    """Tests for extract_jsonld_from_page function."""

    def setup_method(self):
        """Reset request counter before each test."""
        reset_request_counter()

    @patch("src.scrapers.gamestop.check_pause_logic")
    @patch("src.scrapers.gamestop.utils.get_with_retry")
    def test_extracts_store_jsonld(self, mock_get, mock_pause):
        """Test extraction of Store-type JSON-LD from detail page."""
        mock_response = Mock()
        mock_response.text = SAMPLE_DETAIL_HTML
        mock_get.return_value = mock_response

        result = extract_jsonld_from_page(Mock(), "https://example.com/store")

        assert result is not None
        assert result["@type"] == "Store"
        assert result["name"] == "East 14th Street New York"

    @patch("src.scrapers.gamestop.utils.get_with_retry")
    def test_request_failure_returns_none(self, mock_get):
        """Test returns None when request fails."""
        mock_get.return_value = None
        result = extract_jsonld_from_page(Mock(), "https://example.com/store")
        assert result is None

    @patch("src.scrapers.gamestop.check_pause_logic")
    @patch("src.scrapers.gamestop.utils.get_with_retry")
    def test_no_jsonld_returns_none(self, mock_get, mock_pause):
        """Test returns None when no JSON-LD found in page."""
        mock_response = Mock()
        mock_response.text = "<html><body>No JSON-LD here</body></html>"
        mock_get.return_value = mock_response

        result = extract_jsonld_from_page(Mock(), "https://example.com/store")
        assert result is None

    @patch("src.scrapers.gamestop.check_pause_logic")
    @patch("src.scrapers.gamestop.utils.get_with_retry")
    def test_non_store_jsonld_skipped(self, mock_get, mock_pause):
        """Test non-Store JSON-LD types are skipped."""
        html = """
        <script type="application/ld+json">
        {"@type": "Organization", "name": "GameStop"}
        </script>
        """
        mock_response = Mock()
        mock_response.text = html
        mock_get.return_value = mock_response

        result = extract_jsonld_from_page(Mock(), "https://example.com/store")
        assert result is None

    @patch("src.scrapers.gamestop.check_pause_logic")
    @patch("src.scrapers.gamestop.utils.get_with_retry")
    def test_malformed_jsonld_skipped(self, mock_get, mock_pause):
        """Test malformed JSON-LD is skipped gracefully."""
        html = """
        <script type="application/ld+json">
        {invalid json here}
        </script>
        """
        mock_response = Mock()
        mock_response.text = html
        mock_get.return_value = mock_response

        result = extract_jsonld_from_page(Mock(), "https://example.com/store")
        assert result is None

    @patch("src.scrapers.gamestop.check_pause_logic")
    @patch("src.scrapers.gamestop.utils.get_with_retry")
    def test_multiple_jsonld_finds_store(self, mock_get, mock_pause):
        """Test finds Store type among multiple JSON-LD blocks."""
        html = """
        <script type="application/ld+json">
        {"@type": "Organization", "name": "GameStop Corp"}
        </script>
        <script type="application/ld+json">
        {"@type": "Store", "name": "Test Store", "description": "A store"}
        </script>
        """
        mock_response = Mock()
        mock_response.text = html
        mock_get.return_value = mock_response

        result = extract_jsonld_from_page(Mock(), "https://example.com/store")
        assert result is not None
        assert result["@type"] == "Store"
        assert result["name"] == "Test Store"


# =============================================================================
# Enrichment Tests
# =============================================================================


class TestEnrichStore:
    """Tests for enrich_store function."""

    def _make_store(self, store_id="6562"):
        """Create a minimal GameStopStore for testing."""
        return GameStopStore(
            store_id=store_id, name="Test", street_address="123", address2="",
            city="NYC", state="NY", zip_code="10001", country="US",
            latitude=40.7, longitude=-74.0, phone="", store_mode="ACTIVE",
            hours=None, midday_closure=False, description="", knows_about="",
            payment_accepted="", currencies_accepted="", image_url="",
            url="https://example.com/store", scraped_at="",
        )

    def test_enriches_all_fields(self):
        """Test all JSON-LD fields are merged into store."""
        store = self._make_store()
        enrich_store(store, SAMPLE_JSONLD)

        assert "Visit East 14th Street" in store.description
        assert store.image_url == "https://media.gamestop.com/i/gamestop/aff_gme_storefront"
        assert store.currencies_accepted == "USD"
        assert "Video Games" in store.knows_about
        assert "PS5" in store.knows_about
        assert "Cash" in store.payment_accepted
        assert "Credit Card" in store.payment_accepted
        assert store.url == SAMPLE_JSONLD["url"]

    def test_handles_string_payment(self):
        """Test handles paymentAccepted as a string instead of list."""
        store = self._make_store()
        jsonld = {"paymentAccepted": "Cash only"}
        enrich_store(store, jsonld)
        assert store.payment_accepted == "Cash only"

    def test_handles_string_knows_about(self):
        """Test handles knowsAbout as a string instead of list."""
        store = self._make_store()
        jsonld = {"knowsAbout": "Video Games and Consoles"}
        enrich_store(store, jsonld)
        assert store.knows_about == "Video Games and Consoles"

    def test_handles_empty_jsonld(self):
        """Test handles JSON-LD with no enrichment fields."""
        store = self._make_store()
        enrich_store(store, {"@type": "Store"})
        assert store.description == ""
        assert store.knows_about == ""
        assert store.payment_accepted == ""

    def test_canonical_url_updated(self):
        """Test URL is updated from JSON-LD canonical."""
        store = self._make_store()
        store.url = "https://old-url.com"
        enrich_store(store, {"url": "https://canonical.com/store"})
        assert store.url == "https://canonical.com/store"

    def test_no_canonical_url_preserves_original(self):
        """Test original URL preserved when JSON-LD has no url."""
        store = self._make_store()
        store.url = "https://original.com"
        enrich_store(store, {"@type": "Store"})
        assert store.url == "https://original.com"


# =============================================================================
# Enrich All Stores Tests
# =============================================================================


class TestEnrichAllStores:
    """Tests for enrich_all_stores function."""

    def setup_method(self):
        """Reset request counter before each test."""
        reset_request_counter()

    def _make_store(self, store_id, url="https://example.com/store"):
        """Create a minimal GameStopStore for testing."""
        return GameStopStore(
            store_id=store_id, name=f"Store {store_id}", street_address="123",
            address2="", city="NYC", state="NY", zip_code="10001", country="US",
            latitude=40.7, longitude=-74.0, phone="", store_mode="ACTIVE",
            hours=None, midday_closure=False, description="", knows_about="",
            payment_accepted="", currencies_accepted="", image_url="",
            url=url, scraped_at="",
        )

    @patch("src.scrapers.gamestop.utils.random_delay")
    @patch("src.scrapers.gamestop.utils.select_delays")
    @patch("src.scrapers.gamestop.extract_jsonld_from_page")
    def test_enriches_stores(self, mock_extract, mock_delays, mock_delay):
        """Test enrichment fetches JSON-LD for each store."""
        mock_delays.return_value = (0.1, 0.2)
        mock_extract.return_value = SAMPLE_JSONLD

        stores = {
            "6562": self._make_store("6562"),
            "7777": self._make_store("7777"),
        }
        yaml_config = {"proxy": {"mode": "direct"}}

        enrich_all_stores(Mock(), stores, "gamestop", yaml_config)

        assert mock_extract.call_count == 2
        assert "Visit East 14th Street" in stores["6562"].description

    @patch("src.scrapers.gamestop.utils.random_delay")
    @patch("src.scrapers.gamestop.utils.select_delays")
    @patch("src.scrapers.gamestop.extract_jsonld_from_page")
    def test_skips_completed_ids(self, mock_extract, mock_delays, mock_delay):
        """Test stores with completed IDs are skipped."""
        mock_delays.return_value = (0.1, 0.2)
        mock_extract.return_value = SAMPLE_JSONLD

        stores = {
            "6562": self._make_store("6562"),
            "7777": self._make_store("7777"),
        }
        yaml_config = {"proxy": {"mode": "direct"}}

        enrich_all_stores(
            Mock(), stores, "gamestop", yaml_config,
            completed_ids={"6562"},
        )

        assert mock_extract.call_count == 1

    @patch("src.scrapers.gamestop.utils.random_delay")
    @patch("src.scrapers.gamestop.utils.select_delays")
    @patch("src.scrapers.gamestop.extract_jsonld_from_page")
    def test_respects_limit(self, mock_extract, mock_delays, mock_delay):
        """Test limit parameter limits enrichment count."""
        mock_delays.return_value = (0.1, 0.2)
        mock_extract.return_value = SAMPLE_JSONLD

        stores = {
            "1": self._make_store("1"),
            "2": self._make_store("2"),
            "3": self._make_store("3"),
        }
        yaml_config = {"proxy": {"mode": "direct"}}

        enrich_all_stores(
            Mock(), stores, "gamestop", yaml_config, limit=1,
        )

        assert mock_extract.call_count == 1

    @patch("src.scrapers.gamestop.utils.random_delay")
    @patch("src.scrapers.gamestop.utils.select_delays")
    @patch("src.scrapers.gamestop.extract_jsonld_from_page")
    def test_skips_stores_without_url(self, mock_extract, mock_delays, mock_delay):
        """Test stores without a URL are skipped."""
        mock_delays.return_value = (0.1, 0.2)

        stores = {
            "6562": self._make_store("6562", url=""),
            "7777": self._make_store("7777", url="https://example.com/store"),
        }
        yaml_config = {"proxy": {"mode": "direct"}}

        enrich_all_stores(Mock(), stores, "gamestop", yaml_config)

        assert mock_extract.call_count == 1


# =============================================================================
# Run Entry Point Tests
# =============================================================================


class TestRun:
    """Tests for the run() entry point."""

    def setup_method(self):
        """Reset request counter before each test."""
        reset_request_counter()

    @patch("src.scrapers.gamestop.utils.validate_stores_batch")
    @patch("src.scrapers.gamestop.utils.save_checkpoint")
    @patch("src.scrapers.gamestop.enrich_all_stores")
    @patch("src.scrapers.gamestop.discover_all_stores")
    @patch("src.scrapers.gamestop.utils.select_delays")
    def test_full_run(
        self, mock_delays, mock_discover,
        mock_enrich, mock_save_cp, mock_validate
    ):
        """Test full run with discovery and enrichment."""
        mock_delays.return_value = (1.0, 2.0)

        store1 = GameStopStore(
            store_id="6562", name="Store A", street_address="123", address2="",
            city="NYC", state="NY", zip_code="10001", country="US",
            latitude=40.7, longitude=-74.0, phone="(212) 555-0100",
            store_mode="ACTIVE", hours=None, midday_closure=False,
            description="", knows_about="", payment_accepted="",
            currencies_accepted="", image_url="", url="https://example.com",
            scraped_at="",
        )
        mock_discover.return_value = {"6562": store1}

        mock_enrich.return_value = {"6562": store1}
        mock_validate.return_value = {"valid": 1, "total": 1, "warning_count": 0}

        yaml_config = {"proxy": {"mode": "direct"}, "checkpoint_interval": 50}

        result = run(Mock(), yaml_config, retailer="gamestop")

        assert result["count"] == 1
        assert len(result["stores"]) == 1
        assert result["checkpoints_used"] is False
        assert result["stores"][0]["store_id"] == "6562"

    @patch("src.scrapers.gamestop.utils.validate_stores_batch")
    @patch("src.scrapers.gamestop.utils.save_checkpoint")
    @patch("src.scrapers.gamestop.enrich_all_stores")
    @patch("src.scrapers.gamestop.discover_all_stores")
    @patch("src.scrapers.gamestop.utils.select_delays")
    def test_run_always_discovers(
        self, mock_delays, mock_discover,
        mock_enrich, mock_save_cp, mock_validate
    ):
        """Test run always calls discover (no URL cache)."""
        mock_delays.return_value = (1.0, 2.0)

        store1 = GameStopStore(
            store_id="6562", name="Store A", street_address="123", address2="",
            city="NYC", state="NY", zip_code="10001", country="US",
            latitude=40.7, longitude=-74.0, phone="(212) 555-0100",
            store_mode="ACTIVE", hours=None, midday_closure=False,
            description="", knows_about="", payment_accepted="",
            currencies_accepted="", image_url="", url="https://example.com",
            scraped_at="",
        )
        mock_discover.return_value = {"6562": store1}
        mock_enrich.return_value = {"6562": store1}
        mock_validate.return_value = {"valid": 1, "total": 1, "warning_count": 0}

        yaml_config = {"proxy": {"mode": "direct"}, "checkpoint_interval": 50}

        run(Mock(), yaml_config, retailer="gamestop")

        mock_discover.assert_called_once()

    @patch("src.scrapers.gamestop.utils.validate_stores_batch")
    @patch("src.scrapers.gamestop.utils.save_checkpoint")
    @patch("src.scrapers.gamestop.utils.load_checkpoint")
    @patch("src.scrapers.gamestop.enrich_all_stores")
    @patch("src.scrapers.gamestop.discover_all_stores")
    @patch("src.scrapers.gamestop.utils.select_delays")
    def test_run_with_resume(
        self, mock_delays, mock_discover,
        mock_enrich, mock_load_cp, mock_save_cp, mock_validate
    ):
        """Test run resumes from checkpoint."""
        mock_delays.return_value = (1.0, 2.0)

        # Checkpoint has one store done
        mock_load_cp.return_value = {
            "stores": [{"store_id": "6562", "name": "Done"}],
            "completed_ids": ["6562"],
        }

        store2 = GameStopStore(
            store_id="7777", name="Store B", street_address="456", address2="",
            city="LA", state="CA", zip_code="90001", country="US",
            latitude=34.0, longitude=-118.2, phone="",
            store_mode="ACTIVE", hours=None, midday_closure=False,
            description="", knows_about="", payment_accepted="",
            currencies_accepted="", image_url="", url="https://example.com",
            scraped_at="",
        )
        mock_discover.return_value = {"6562": Mock(), "7777": store2}
        mock_enrich.return_value = {"6562": Mock(), "7777": store2}
        mock_validate.return_value = {"valid": 2, "total": 2, "warning_count": 0}

        yaml_config = {"proxy": {"mode": "direct"}, "checkpoint_interval": 50}

        result = run(Mock(), yaml_config, retailer="gamestop", resume=True)

        assert result["checkpoints_used"] is True
        assert result["count"] == 2

    @patch("src.scrapers.gamestop.utils.validate_stores_batch")
    @patch("src.scrapers.gamestop.utils.save_checkpoint")
    @patch("src.scrapers.gamestop.enrich_all_stores")
    @patch("src.scrapers.gamestop.discover_all_stores")
    @patch("src.scrapers.gamestop.utils.select_delays")
    def test_run_with_limit(
        self, mock_delays, mock_discover,
        mock_enrich, mock_save_cp, mock_validate
    ):
        """Test run respects store limit."""
        mock_delays.return_value = (1.0, 2.0)

        stores_dict = {}
        for i in range(10):
            sid = str(1000 + i)
            stores_dict[sid] = GameStopStore(
                store_id=sid, name=f"Store {sid}", street_address="x",
                address2="", city="C", state="NY", zip_code="10001",
                country="US", latitude=40.7, longitude=-74.0, phone="",
                store_mode="ACTIVE", hours=None, midday_closure=False,
                description="", knows_about="", payment_accepted="",
                currencies_accepted="", image_url="",
                url="https://example.com", scraped_at="",
            )
        mock_discover.return_value = stores_dict

        mock_enrich.return_value = stores_dict
        mock_validate.return_value = {"valid": 3, "total": 3, "warning_count": 0}

        yaml_config = {"proxy": {"mode": "direct"}, "checkpoint_interval": 50}

        result = run(Mock(), yaml_config, retailer="gamestop", limit=3)

        assert result["count"] == 3

    @patch("src.scrapers.gamestop.discover_all_stores")
    @patch("src.scrapers.gamestop.utils.select_delays")
    def test_run_no_stores_returns_empty(
        self, mock_delays, mock_discover
    ):
        """Test run returns empty when no stores discovered."""
        mock_delays.return_value = (1.0, 2.0)

        mock_discover.return_value = {}

        yaml_config = {"proxy": {"mode": "direct"}, "checkpoint_interval": 50}

        result = run(Mock(), yaml_config, retailer="gamestop")

        assert result["count"] == 0
        assert result["stores"] == []


# =============================================================================
# Config Module Tests
# =============================================================================


class TestGameStopConfig:
    """Tests for gamestop_config module."""

    def test_grid_covers_conus(self):
        """Test grid has enough points to cover continental US."""
        grid = gamestop_config.generate_us_grid()
        # Design doc estimates ~84 CONUS + 6 extra = ~90 total
        assert len(grid) >= 80

    def test_grid_includes_extra_points(self):
        """Test grid includes Alaska, Hawaii, Puerto Rico, Guam."""
        grid = gamestop_config.generate_us_grid()
        lats = [p[0] for p in grid]
        lngs = [p[1] for p in grid]

        # Alaska (lat > 60)
        assert any(lat > 60 for lat in lats)
        # Hawaii (lat < 22 and lng < -150)
        assert any(lat < 22 and lng < -150 for lat, lng in grid)
        # Puerto Rico (lat ~18, lng ~-66)
        assert any(17 < lat < 19 and -67 < lng < -65 for lat, lng in grid)
        # Guam (lat ~13, lng ~144)
        assert any(13 < lat < 14 and 144 < lng < 145 for lat, lng in grid)

    def test_grid_conus_bounds(self):
        """Test CONUS grid points are within US bounds."""
        grid = gamestop_config.generate_us_grid()
        # Filter to just CONUS points (exclude extra points)
        conus = [p for p in grid if p not in gamestop_config.EXTRA_GRID_POINTS]

        for lat, lng in conus:
            assert gamestop_config.US_BOUNDS["lat_min"] <= lat <= gamestop_config.US_BOUNDS["lat_max"]
            assert gamestop_config.US_BOUNDS["lng_min"] <= lng <= gamestop_config.US_BOUNDS["lng_max"]

    def test_build_api_url(self):
        """Test API URL construction."""
        url = gamestop_config.build_api_url(40.7, -74.0)
        assert "Stores-FindStores" in url
        assert "lat=40.7" in url
        assert "long=-74.0" in url
        assert "radius=200" in url

    def test_build_api_url_custom_radius(self):
        """Test API URL with custom radius."""
        url = gamestop_config.build_api_url(40.7, -74.0, radius=100)
        assert "radius=100" in url

    def test_build_store_detail_url(self):
        """Test store detail URL construction."""
        url = gamestop_config.build_store_detail_url(
            "NY", "New York", "6562", "East 14th Street New York"
        )
        assert "/store/us/ny/" in url
        assert "/new-york/" in url
        assert "/6562/" in url
        assert url.endswith("-gamestop")

    def test_build_store_detail_url_special_chars(self):
        """Test URL slugification handles special characters."""
        url = gamestop_config.build_store_detail_url(
            "CA", "San Francisco", "1234", "Store #5 - Main St."
        )
        assert "/san-francisco/" in url
        assert "#" not in url
        assert "." not in url.split("/")[-1].replace("-gamestop", "")

    def test_slugify(self):
        """Test slugification function."""
        assert gamestop_config._slugify("New York City") == "new-york-city"
        assert gamestop_config._slugify("San Jose") == "san-jose"
        assert gamestop_config._slugify("Store #5") == "store-5"
        assert gamestop_config._slugify("  spaces  ") == "spaces"

    def test_get_headers_returns_dict(self):
        """Test headers function returns valid headers dict."""
        headers = gamestop_config.get_headers()
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Referer" in headers

    def test_get_page_headers_returns_dict(self):
        """Test page headers have HTML accept type."""
        headers = gamestop_config.get_page_headers()
        assert "text/html" in headers["Accept"]

    def test_store_url_regex_matches(self):
        """Test store URL regex matches expected format."""
        html = '<a href="/store/us/ny/new-york/6562/test-gamestop">'
        matches = gamestop_config.STORE_URL_REGEX.findall(html)
        assert len(matches) == 1
        assert "/store/us/ny/new-york/6562/test-gamestop" in matches[0]

    def test_jsonld_regex_matches(self):
        """Test JSON-LD regex extracts script content."""
        html = '<script type="application/ld+json">{"@type":"Store"}</script>'
        matches = gamestop_config.JSONLD_REGEX.findall(html)
        assert len(matches) == 1
        assert '"@type":"Store"' in matches[0]

    def test_us_bounds_valid(self):
        """Test US bounds are geographically valid."""
        bounds = gamestop_config.US_BOUNDS
        assert bounds["lat_min"] < bounds["lat_max"]
        assert bounds["lng_min"] < bounds["lng_max"]
        assert bounds["lat_min"] > 0  # Northern hemisphere
        assert bounds["lng_min"] < 0  # Western hemisphere

    def test_constants_reasonable(self):
        """Test configuration constants have reasonable values."""
        assert gamestop_config.SEARCH_RADIUS_MILES == 200
        assert gamestop_config.LAT_STEP > 0
        assert gamestop_config.LNG_STEP > 0
        assert gamestop_config.MAX_RETRIES > 0
        assert gamestop_config.TIMEOUT > 0
