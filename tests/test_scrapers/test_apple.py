"""Unit tests for Apple retail store scraper."""
# pylint: disable=no-member

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.scrapers.apple import (
    AppleStore,
    get_build_id,
    get_store_directory,
    extract_store_detail,
    _parse_hours,
    _parse_services,
    _parse_programs,
    _get_hero_image_url,
    _build_store_from_directory,
    run,
    reset_request_counter,
)
from config import apple_config as config


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------

SAMPLE_BUILD_ID = "WvJEhhQSiVnNziWwWdN-K"

SAMPLE_DIRECTORY_STORE = {
    "id": "R001",
    "name": "Glendale Galleria",
    "slug": "glendalegalleria",
    "telephone": "(818) 507-6338",
    "address": {
        "address1": "2148 Glendale Galleria",
        "address2": "",
        "city": "Glendale",
        "postalCode": "91210",
        "stateName": "California",
        "stateCode": "CA",
        "__typename": "PostalAddress",
    },
    "__typename": "RgdsStore",
}

SAMPLE_STORE_DETAIL = {
    "storeNumber": "R001",
    "locale": "en_US",
    "name": "Glendale Galleria",
    "slug": "glendalegalleria",
    "timezone": "America/Los_Angeles",
    "telephone": "(818) 507-6338",
    "email": "glendalegalleria@apple.com",
    "geolocation": {"latitude": 34.14778, "longitude": -118.25298},
    "address": {
        "address1": "2148 Glendale Galleria",
        "address2": "",
        "city": "Glendale",
        "stateCode": "CA",
        "stateName": "California",
        "postal": "91210",
    },
    "hours": {
        "alwaysOpen": False,
        "closed": False,
        "currentStatus": "Open until 9:00 p.m.",
        "days": [
            {
                "name": "Today",
                "formattedDate": "Feb 5",
                "formattedTime": "10:00 a.m. - 9:00 p.m.",
                "specialHours": False,
            },
            {
                "name": "Tomorrow",
                "formattedDate": "Feb 6",
                "formattedTime": "10:00 a.m. - 9:00 p.m.",
                "specialHours": False,
            },
        ],
    },
    "operatingModel": {
        "operatingModelId": "BAU01",
        "instore": {
            "Shopping": {"services": ["SHOP", "TradeIn"]},
            "Support": {"services": ["GBDI", "GB"]},
        },
    },
    "heroImage": {
        "large": {"x2": "https://rtlimages.apple.com/cmc/dieter/store/16_9/R001.png"},
        "medium": {"x2": "https://rtlimages.apple.com/cmc/dieter/store/4_3/R001.png"},
        "small": {"x2": "https://rtlimages.apple.com/cmc/dieter/store/1_1/R001.png"},
    },
    "programs": [
        {"id": "Shop", "header": "Come see the best of Apple."},
        {"id": "Support", "header": "We'll help you get started."},
    ],
}


def _make_storelist_html(build_id=SAMPLE_BUILD_ID):
    """Create HTML with embedded __NEXT_DATA__ containing buildId."""
    return f"""<!DOCTYPE html>
<html>
<head><title>Apple Store List</title></head>
<body>
<script id="__NEXT_DATA__" type="application/json">
{{"buildId":"{build_id}","props":{{"pageProps":{{}}}}}}
</script>
</body>
</html>"""


def _make_storelist_json(us_stores=None, extra_locales=None):
    """Create storelist.json response data."""
    if us_stores is None:
        us_stores = [SAMPLE_DIRECTORY_STORE]

    states = {}
    for store in us_stores:
        state_name = store.get("address", {}).get("stateName", "Unknown")
        if state_name not in states:
            states[state_name] = []
        states[state_name].append(store)

    state_list = [
        {"__typename": "RgdsState", "name": name, "store": stores}
        for name, stores in states.items()
    ]

    store_list = [
        {
            "locale": "en_US",
            "calledLocale": "en_US",
            "hasStates": True,
            "state": state_list,
        }
    ]

    if extra_locales:
        store_list.extend(extra_locales)

    return {"pageProps": {"storeList": store_list}}


def _make_detail_page_html(store_detail=None):
    """Create store detail page HTML with __NEXT_DATA__ blob."""
    if store_detail is None:
        store_detail = SAMPLE_STORE_DETAIL

    next_data = json.dumps({
        "props": {"pageProps": {"storeDetails": store_detail}}
    })

    return f"""<!DOCTYPE html>
<html>
<head><title>Apple Store - {store_detail.get('name', 'Store')}</title></head>
<body>
<script id="__NEXT_DATA__" type="application/json">{next_data}</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# TestAppleStore
# ---------------------------------------------------------------------------

class TestAppleStore:
    """Tests for AppleStore dataclass."""

    def test_to_dict_full_data(self):
        """Test dict conversion with all fields populated."""
        store = AppleStore(
            store_id="R001",
            name="Glendale Galleria",
            slug="glendalegalleria",
            street_address="2148 Glendale Galleria",
            address2="",
            city="Glendale",
            state="CA",
            state_name="California",
            zip_code="91210",
            country="US",
            phone="(818) 507-6338",
            email="glendalegalleria@apple.com",
            latitude=34.14778,
            longitude=-118.25298,
            timezone="America/Los_Angeles",
            hours='[{"name":"Today","hours":"10:00 a.m. - 9:00 p.m."}]',
            current_status="Open until 9:00 p.m.",
            services='{"Shopping":["SHOP","TradeIn"]}',
            operating_model="BAU01",
            hero_image_url="https://rtlimages.apple.com/cmc/dieter/store/16_9/R001.png",
            programs='[{"id":"Shop","header":"Come see the best of Apple."}]',
            url="https://www.apple.com/retail/glendalegalleria/",
            scraped_at="2026-02-05T12:00:00",
        )
        result = store.to_dict()

        assert result["store_id"] == "R001"
        assert result["name"] == "Glendale Galleria"
        assert result["state"] == "CA"
        assert result["latitude"] == "34.14778"
        assert result["longitude"] == "-118.25298"
        assert result["timezone"] == "America/Los_Angeles"
        assert result["operating_model"] == "BAU01"

    def test_to_dict_missing_coordinates(self):
        """Test dict conversion with None coordinates becomes empty strings."""
        store = AppleStore(
            store_id="R002",
            name="Test Store",
            slug="teststore",
            street_address="123 Main St",
            address2="",
            city="TestCity",
            state="TX",
            state_name="Texas",
            zip_code="75001",
            country="US",
            phone="",
            email="",
            latitude=None,
            longitude=None,
            timezone="",
            hours=None,
            current_status="",
            services=None,
            operating_model="",
            hero_image_url="",
            programs=None,
            url="https://www.apple.com/retail/teststore/",
            scraped_at="2026-02-05T12:00:00",
        )
        result = store.to_dict()

        assert result["latitude"] == ""
        assert result["longitude"] == ""


# ---------------------------------------------------------------------------
# TestGetBuildId
# ---------------------------------------------------------------------------

class TestGetBuildId:
    """Tests for get_build_id function."""

    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_extracts_build_id(self, mock_get, mock_counter):
        """Test successful buildId extraction from HTML."""
        mock_response = Mock()
        mock_response.text = _make_storelist_html(SAMPLE_BUILD_ID)
        mock_get.return_value = mock_response

        result = get_build_id(Mock())

        assert result == SAMPLE_BUILD_ID

    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_returns_none_on_failed_fetch(self, mock_get, mock_counter):
        """Test returns None when page fetch fails."""
        mock_get.return_value = None

        result = get_build_id(Mock())

        assert result is None

    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_returns_none_when_build_id_missing(self, mock_get, mock_counter):
        """Test returns None when buildId not found in HTML."""
        mock_response = Mock()
        mock_response.text = "<html><body>No build id here</body></html>"
        mock_get.return_value = mock_response

        result = get_build_id(Mock())

        assert result is None


# ---------------------------------------------------------------------------
# TestGetStoreDirectory
# ---------------------------------------------------------------------------

class TestGetStoreDirectory:
    """Tests for get_store_directory function."""

    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_parses_us_stores(self, mock_get, mock_counter):
        """Test parsing US stores from directory response."""
        store2 = {**SAMPLE_DIRECTORY_STORE, "id": "R002", "name": "The Grove", "slug": "thegrove"}
        mock_response = Mock()
        mock_response.json.return_value = _make_storelist_json([SAMPLE_DIRECTORY_STORE, store2])
        mock_get.return_value = mock_response

        result = get_store_directory(Mock(), SAMPLE_BUILD_ID)

        assert len(result) == 2
        assert result[0]["id"] == "R001"
        assert result[1]["id"] == "R002"

    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_returns_empty_on_failed_fetch(self, mock_get, mock_counter):
        """Test returns empty list on fetch failure."""
        mock_get.return_value = None

        result = get_store_directory(Mock(), SAMPLE_BUILD_ID)

        assert result == []

    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_returns_empty_when_no_us_locale(self, mock_get, mock_counter):
        """Test returns empty when US locale not in response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "pageProps": {
                "storeList": [
                    {"locale": "en_GB", "state": []}
                ]
            }
        }
        mock_get.return_value = mock_response

        result = get_store_directory(Mock(), SAMPLE_BUILD_ID)

        assert result == []

    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_handles_malformed_json(self, mock_get, mock_counter):
        """Test handles malformed JSON gracefully."""
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("err", "doc", 0)
        mock_get.return_value = mock_response

        result = get_store_directory(Mock(), SAMPLE_BUILD_ID)

        assert result == []

    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_flattens_stores_from_multiple_states(self, mock_get, mock_counter):
        """Test that stores from multiple states are all extracted."""
        store_ca = {
            **SAMPLE_DIRECTORY_STORE,
            "id": "R001",
            "address": {**SAMPLE_DIRECTORY_STORE["address"], "stateName": "California"},
        }
        store_ny = {
            **SAMPLE_DIRECTORY_STORE,
            "id": "R250",
            "name": "West 14th Street",
            "slug": "west14thstreet",
            "address": {
                **SAMPLE_DIRECTORY_STORE["address"],
                "stateName": "New York",
                "stateCode": "NY",
                "city": "New York",
            },
        }
        mock_response = Mock()
        mock_response.json.return_value = _make_storelist_json([store_ca, store_ny])
        mock_get.return_value = mock_response

        result = get_store_directory(Mock(), SAMPLE_BUILD_ID)

        assert len(result) == 2
        ids = {s["id"] for s in result}
        assert ids == {"R001", "R250"}


# ---------------------------------------------------------------------------
# TestParseHours
# ---------------------------------------------------------------------------

class TestParseHours:
    """Tests for _parse_hours function."""

    def test_valid_hours(self):
        """Test parsing valid hours data."""
        hours_data = {
            "days": [
                {
                    "name": "Today",
                    "formattedDate": "Feb 5",
                    "formattedTime": "10:00 a.m. - 9:00 p.m.",
                    "specialHours": False,
                },
            ]
        }
        result = _parse_hours(hours_data)
        parsed = json.loads(result)

        assert len(parsed) == 1
        assert parsed[0]["name"] == "Today"
        assert parsed[0]["hours"] == "10:00 a.m. - 9:00 p.m."
        assert parsed[0]["special"] is False

    def test_empty_hours(self):
        """Test returns None for empty hours data."""
        assert _parse_hours({}) is None
        assert _parse_hours(None) is None

    def test_empty_days_list(self):
        """Test returns None when days list is empty."""
        assert _parse_hours({"days": []}) is None

    def test_special_hours(self):
        """Test parsing special hours flag."""
        hours_data = {
            "days": [
                {
                    "name": "Monday",
                    "formattedDate": "Feb 10",
                    "formattedTime": "Closed",
                    "specialHours": True,
                },
            ]
        }
        result = _parse_hours(hours_data)
        parsed = json.loads(result)

        assert parsed[0]["special"] is True
        assert parsed[0]["hours"] == "Closed"


# ---------------------------------------------------------------------------
# TestParseServices
# ---------------------------------------------------------------------------

class TestParseServices:
    """Tests for _parse_services function."""

    def test_valid_services(self):
        """Test parsing valid operating model services."""
        model = {
            "instore": {
                "Shopping": {"services": ["SHOP", "TradeIn"]},
                "Support": {"services": ["GBDI"]},
            }
        }
        result = _parse_services(model)
        parsed = json.loads(result)

        assert parsed["Shopping"] == ["SHOP", "TradeIn"]
        assert parsed["Support"] == ["GBDI"]

    def test_empty_model(self):
        """Test returns None for empty operating model."""
        assert _parse_services({}) is None
        assert _parse_services(None) is None

    def test_no_instore(self):
        """Test returns None when instore key missing."""
        assert _parse_services({"operatingModelId": "BAU01"}) is None


# ---------------------------------------------------------------------------
# TestParsePrograms
# ---------------------------------------------------------------------------

class TestParsePrograms:
    """Tests for _parse_programs function."""

    def test_valid_programs(self):
        """Test parsing valid programs list."""
        programs = [
            {"id": "Shop", "header": "Come see the best of Apple."},
            {"id": "Support", "header": "We'll help you."},
        ]
        result = _parse_programs(programs)
        parsed = json.loads(result)

        assert len(parsed) == 2
        assert parsed[0]["id"] == "Shop"

    def test_empty_programs(self):
        """Test returns None for empty programs."""
        assert _parse_programs([]) is None
        assert _parse_programs(None) is None


# ---------------------------------------------------------------------------
# TestGetHeroImageUrl
# ---------------------------------------------------------------------------

class TestGetHeroImageUrl:
    """Tests for _get_hero_image_url function."""

    def test_prefers_large_image(self):
        """Test prefers large x2 image."""
        hero = {
            "large": {"x2": "https://example.com/large.png"},
            "medium": {"x2": "https://example.com/medium.png"},
        }
        assert _get_hero_image_url(hero) == "https://example.com/large.png"

    def test_falls_back_to_medium(self):
        """Test falls back to medium when large unavailable."""
        hero = {
            "large": {},
            "medium": {"x2": "https://example.com/medium.png"},
        }
        assert _get_hero_image_url(hero) == "https://example.com/medium.png"

    def test_falls_back_to_small(self):
        """Test falls back to small when others unavailable."""
        hero = {
            "small": {"x2": "https://example.com/small.png"},
        }
        assert _get_hero_image_url(hero) == "https://example.com/small.png"

    def test_falls_back_to_x1_when_x2_unavailable(self):
        """Test falls back to x1 resolution when x2 is missing."""
        hero = {
            "large": {"x1": "https://example.com/large_x1.png"},
        }
        assert _get_hero_image_url(hero) == "https://example.com/large_x1.png"

    def test_returns_empty_for_none(self):
        """Test returns empty string for None input."""
        assert _get_hero_image_url(None) == ""
        assert _get_hero_image_url({}) == ""


# ---------------------------------------------------------------------------
# TestExtractStoreDetail
# ---------------------------------------------------------------------------

class TestExtractStoreDetail:
    """Tests for extract_store_detail function."""

    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_extracts_full_store_detail(self, mock_get, mock_counter):
        """Test extracting complete store detail data."""
        mock_response = Mock()
        mock_response.text = _make_detail_page_html()
        mock_get.return_value = mock_response

        store = extract_store_detail(Mock(), "glendalegalleria", SAMPLE_DIRECTORY_STORE)

        assert store is not None
        assert store.store_id == "R001"
        assert store.name == "Glendale Galleria"
        assert store.slug == "glendalegalleria"
        assert store.city == "Glendale"
        assert store.state == "CA"
        assert store.state_name == "California"
        assert store.zip_code == "91210"
        assert store.latitude == 34.14778
        assert store.longitude == -118.25298
        assert store.timezone == "America/Los_Angeles"
        assert store.operating_model == "BAU01"
        assert store.email == "glendalegalleria@apple.com"
        assert "rtlimages.apple.com" in store.hero_image_url

        # Verify hours are parsed
        hours = json.loads(store.hours)
        assert len(hours) == 2
        assert hours[0]["name"] == "Today"

        # Verify services are parsed
        services = json.loads(store.services)
        assert "Shopping" in services
        assert "SHOP" in services["Shopping"]

    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_falls_back_to_directory_on_fetch_failure(self, mock_get, mock_counter):
        """Test fallback to directory data when detail page fetch fails."""
        mock_get.return_value = None

        store = extract_store_detail(Mock(), "glendalegalleria", SAMPLE_DIRECTORY_STORE)

        assert store is not None
        assert store.store_id == "R001"
        assert store.name == "Glendale Galleria"
        assert store.latitude is None  # Not available from directory
        assert store.timezone == ""  # Not available from directory

    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_falls_back_on_missing_next_data(self, mock_get, mock_counter):
        """Test fallback when __NEXT_DATA__ not found in HTML."""
        mock_response = Mock()
        mock_response.text = "<html><body>No data here</body></html>"
        mock_get.return_value = mock_response

        store = extract_store_detail(Mock(), "teststore", SAMPLE_DIRECTORY_STORE)

        assert store is not None
        assert store.store_id == "R001"  # From directory data

    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_falls_back_on_missing_store_details(self, mock_get, mock_counter):
        """Test fallback when storeDetails key missing in __NEXT_DATA__."""
        next_data = json.dumps({"props": {"pageProps": {}}})
        mock_response = Mock()
        mock_response.text = (
            f'<script id="__NEXT_DATA__" type="application/json">{next_data}</script>'
        )
        mock_get.return_value = mock_response

        store = extract_store_detail(Mock(), "teststore", SAMPLE_DIRECTORY_STORE)

        assert store is not None
        assert store.latitude is None  # Fallback, no detail enrichment

    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_handles_partial_store_data(self, mock_get, mock_counter):
        """Test handling of store detail with missing optional fields."""
        minimal_detail = {
            "storeNumber": "R999",
            "name": "Minimal Store",
            "slug": "minimalstore",
            "address": {"city": "Somewhere"},
        }
        mock_response = Mock()
        mock_response.text = _make_detail_page_html(minimal_detail)
        mock_get.return_value = mock_response

        store = extract_store_detail(Mock(), "minimalstore", {"id": "R999", "name": "Minimal", "slug": "minimalstore", "telephone": "", "address": {}})

        assert store is not None
        assert store.store_id == "R999"
        assert store.city == "Somewhere"
        assert store.latitude is None
        assert store.timezone == ""
        assert store.hours is None
        assert store.services is None


# ---------------------------------------------------------------------------
# TestBuildStoreFromDirectory
# ---------------------------------------------------------------------------

class TestBuildStoreFromDirectory:
    """Tests for _build_store_from_directory fallback function."""

    def test_builds_from_directory_data(self):
        """Test building store from directory data only."""
        store = _build_store_from_directory(
            SAMPLE_DIRECTORY_STORE,
            "glendalegalleria",
            "https://www.apple.com/retail/glendalegalleria/",
        )

        assert store.store_id == "R001"
        assert store.name == "Glendale Galleria"
        assert store.city == "Glendale"
        assert store.state == "CA"
        assert store.zip_code == "91210"
        assert store.latitude is None
        assert store.timezone == ""

    def test_handles_empty_directory_data(self):
        """Test building store from empty directory data."""
        store = _build_store_from_directory({}, "testslug", "https://example.com/store")

        assert store.store_id == ""
        assert store.name == ""
        assert store.slug == "testslug"


# ---------------------------------------------------------------------------
# TestAppleConfig
# ---------------------------------------------------------------------------

class TestAppleConfig:
    """Tests for Apple configuration module."""

    def test_build_storelist_url(self):
        """Test building storelist URL with build ID."""
        url = config.build_storelist_url("abc123")

        assert "apple.com/retail/_next/data/abc123/storelist.json" in url

    def test_build_store_detail_url(self):
        """Test building store detail URL from slug."""
        url = config.build_store_detail_url("glendalegalleria")

        assert url == "https://www.apple.com/retail/glendalegalleria/"

    def test_build_graphql_url(self):
        """Test building GraphQL URL with coordinates."""
        url = config.build_graphql_url(40.7505, -74.0027)

        assert "api-www/graphql" in url
        assert "StoreSearchByLocation" in url
        assert "persistedQuery" in url

    def test_build_store_detail_url_sanitizes_bad_slug(self):
        """Test slug with path traversal characters is sanitized."""
        url = config.build_store_detail_url("../admin")

        assert "../" not in url
        assert "admin" in url

    def test_build_storelist_url_rejects_bad_build_id(self):
        """Test build ID with path traversal is rejected."""
        with pytest.raises(ValueError):
            config.build_storelist_url("../../../etc/passwd")

    def test_get_headers(self):
        """Test HTML headers function."""
        headers = config.get_headers()

        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "apple.com" in headers.get("Referer", "")

    def test_get_json_headers(self):
        """Test JSON API headers function."""
        headers = config.get_json_headers()

        assert headers["Accept"] == "application/json"

    def test_get_graphql_headers(self):
        """Test GraphQL headers include CSRF headers."""
        headers = config.get_graphql_headers()

        assert headers["x-apollo-operation-name"] == "StoreSearchByLocation"
        assert headers["apollo-require-preflight"] == "true"
        assert headers["Accept"] == "application/json"


# ---------------------------------------------------------------------------
# TestAppleRun
# ---------------------------------------------------------------------------

class TestAppleRun:
    """Tests for Apple run() function."""

    def _make_directory_response(self, stores=None):
        """Helper to create a storelist.json mock response."""
        if stores is None:
            stores = [SAMPLE_DIRECTORY_STORE]
        response = Mock()
        response.json.return_value = _make_storelist_json(stores)
        return response

    def _make_build_id_response(self, build_id=SAMPLE_BUILD_ID):
        """Helper to create a build ID page response."""
        response = Mock()
        response.text = _make_storelist_html(build_id)
        return response

    def _make_detail_response(self, store_detail=None):
        """Helper to create a store detail page response."""
        response = Mock()
        response.text = _make_detail_page_html(store_detail)
        return response

    @patch("src.scrapers.apple.URLCache")
    @patch("src.scrapers.apple.utils.save_checkpoint")
    @patch("src.scrapers.apple.utils.random_delay")
    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_run_returns_correct_structure(
        self, mock_get, mock_counter, mock_delay, mock_save_cp, mock_cache_class
    ):
        """Test run() returns expected {stores, count, checkpoints_used} structure."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_get.side_effect = [
            self._make_build_id_response(),
            self._make_directory_response(),
            self._make_detail_response(),
        ]

        result = run(Mock(), {"checkpoint_interval": 100}, retailer="apple")

        assert isinstance(result, dict)
        assert "stores" in result
        assert "count" in result
        assert "checkpoints_used" in result
        assert isinstance(result["stores"], list)
        assert isinstance(result["count"], int)
        assert result["checkpoints_used"] is False

    @patch("src.scrapers.apple.URLCache")
    @patch("src.scrapers.apple.utils.save_checkpoint")
    @patch("src.scrapers.apple.utils.random_delay")
    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_run_enriches_store_data(
        self, mock_get, mock_counter, mock_delay, mock_save_cp, mock_cache_class
    ):
        """Test run() enriches stores with detail page data."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_get.side_effect = [
            self._make_build_id_response(),
            self._make_directory_response(),
            self._make_detail_response(),
        ]

        result = run(Mock(), {"checkpoint_interval": 100}, retailer="apple")

        assert result["count"] == 1
        store = result["stores"][0]
        assert store["store_id"] == "R001"
        assert store["latitude"] == "34.14778"
        assert store["timezone"] == "America/Los_Angeles"

    @patch("src.scrapers.apple.URLCache")
    @patch("src.scrapers.apple.utils.save_checkpoint")
    @patch("src.scrapers.apple.utils.random_delay")
    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_run_with_limit(
        self, mock_get, mock_counter, mock_delay, mock_save_cp, mock_cache_class
    ):
        """Test run() respects limit parameter."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        store2 = {**SAMPLE_DIRECTORY_STORE, "id": "R002", "slug": "thegrove"}
        store3 = {**SAMPLE_DIRECTORY_STORE, "id": "R003", "slug": "centurycity"}

        mock_get.side_effect = [
            self._make_build_id_response(),
            self._make_directory_response([SAMPLE_DIRECTORY_STORE, store2, store3]),
            self._make_detail_response(),
            self._make_detail_response(),
        ]

        result = run(Mock(), {"checkpoint_interval": 100}, retailer="apple", limit=2)

        assert result["count"] == 2

    @patch("src.scrapers.apple.URLCache")
    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_run_no_build_id(self, mock_get, mock_counter, mock_cache_class):
        """Test run() returns empty when buildId cannot be extracted."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_response = Mock()
        mock_response.text = "<html>No build id</html>"
        mock_get.return_value = mock_response

        result = run(Mock(), {"checkpoint_interval": 100}, retailer="apple")

        assert result["stores"] == []
        assert result["count"] == 0

    @patch("src.scrapers.apple.URLCache")
    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_run_empty_directory(self, mock_get, mock_counter, mock_cache_class):
        """Test run() returns empty when directory has no stores."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_get.side_effect = [
            self._make_build_id_response(),
            Mock(json=Mock(return_value={"pageProps": {"storeList": []}})),
        ]

        result = run(Mock(), {"checkpoint_interval": 100}, retailer="apple")

        assert result["stores"] == []
        assert result["count"] == 0

    @patch("src.scrapers.apple.URLCache")
    @patch("src.scrapers.apple.utils.save_checkpoint")
    @patch("src.scrapers.apple.utils.random_delay")
    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_run_uses_cached_slugs(
        self, mock_get, mock_counter, mock_delay, mock_save_cp, mock_cache_class
    ):
        """Test run() uses cached slugs and skips directory fetch."""
        mock_cache = Mock()
        mock_cache.get.return_value = ["glendalegalleria"]
        mock_cache_class.return_value = mock_cache

        # Only detail page response needed (no buildId or directory fetch)
        mock_get.side_effect = [
            self._make_detail_response(),
        ]

        result = run(Mock(), {"checkpoint_interval": 100}, retailer="apple")

        assert result["count"] == 1
        # Should not have called get_with_retry for buildId or directory
        assert mock_get.call_count == 1

    @patch("src.scrapers.apple.URLCache")
    @patch("src.scrapers.apple.utils.load_checkpoint")
    @patch("src.scrapers.apple.utils.save_checkpoint")
    @patch("src.scrapers.apple.utils.random_delay")
    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_run_with_resume(
        self, mock_get, mock_counter, mock_delay, mock_save_cp, mock_load_cp, mock_cache_class
    ):
        """Test run() resumes from checkpoint."""
        mock_cache = Mock()
        mock_cache.get.return_value = ["glendalegalleria", "thegrove"]
        mock_cache_class.return_value = mock_cache

        mock_load_cp.return_value = {
            "stores": [{"store_id": "R001", "slug": "glendalegalleria"}],
            "completed_slugs": ["glendalegalleria"],
        }

        # Only one detail page for remaining store
        mock_get.side_effect = [
            self._make_detail_response(),
        ]

        result = run(
            Mock(),
            {"checkpoint_interval": 100},
            retailer="apple",
            resume=True,
        )

        assert result["checkpoints_used"] is True
        assert result["count"] == 2  # 1 from checkpoint + 1 new

    @patch("src.scrapers.apple.URLCache")
    @patch("src.scrapers.apple.utils.save_checkpoint")
    @patch("src.scrapers.apple.utils.random_delay")
    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_run_test_mode_limits_stores(
        self, mock_get, mock_counter, mock_delay, mock_save_cp, mock_cache_class
    ):
        """Test run() in test mode applies TEST_MODE.STORE_LIMIT."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        # Create 15 stores in directory
        many_stores = [
            {**SAMPLE_DIRECTORY_STORE, "id": f"R{i:03d}", "slug": f"store{i}"}
            for i in range(15)
        ]

        detail_responses = [self._make_detail_response() for _ in range(10)]
        mock_get.side_effect = [
            self._make_build_id_response(),
            self._make_directory_response(many_stores),
            *detail_responses,
        ]

        result = run(Mock(), {"checkpoint_interval": 100}, retailer="apple", test=True)

        # TEST_MODE.STORE_LIMIT is 10
        assert result["count"] == 10

    @patch("src.scrapers.apple.URLCache")
    @patch("src.scrapers.apple.utils.save_checkpoint")
    @patch("src.scrapers.apple.utils.random_delay")
    @patch("src.scrapers.apple._request_counter")
    @patch("src.scrapers.apple.utils.get_with_retry")
    def test_run_refresh_urls_skips_cache(
        self, mock_get, mock_counter, mock_delay, mock_save_cp, mock_cache_class
    ):
        """Test run() with refresh_urls=True ignores URL cache."""
        mock_cache = Mock()
        mock_cache.get.return_value = ["oldslug"]  # Cached data exists
        mock_cache_class.return_value = mock_cache

        mock_get.side_effect = [
            self._make_build_id_response(),
            self._make_directory_response(),
            self._make_detail_response(),
        ]

        result = run(
            Mock(),
            {"checkpoint_interval": 100},
            retailer="apple",
            refresh_urls=True,
        )

        # Should have fetched buildId + directory + detail (3 calls)
        assert mock_get.call_count == 3
        # Cache.get should NOT have been called (refresh_urls=True skips cache)
        mock_cache.get.assert_not_called()
