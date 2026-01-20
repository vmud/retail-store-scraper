"""Unit tests for Verizon scraper."""

import pytest
from unittest.mock import Mock, patch

from src.scrapers.verizon import (
    StateConfig,
    VALID_STATE_SLUGS,
    STATE_SLUG_TO_NAME,
    STATE_URL_PATTERNS,
    get_state_url,
    _STATES,
)


class TestStateConfiguration:
    """Tests for state configuration data structures."""

    def test_state_config_dataclass(self):
        """Test StateConfig dataclass creation."""
        config = StateConfig(slug='california', name='California')
        assert config.slug == 'california'
        assert config.name == 'California'
        assert config.url_pattern is None

    def test_state_config_with_url_pattern(self):
        """Test StateConfig with custom URL pattern."""
        config = StateConfig(
            slug='north-carolina',
            name='North Carolina',
            url_pattern='/stores/north-carolina/'
        )
        assert config.url_pattern == '/stores/north-carolina/'

    def test_valid_state_slugs_count(self):
        """Test that we have all 51 state slugs (50 states + DC)."""
        assert len(VALID_STATE_SLUGS) == 51

    def test_valid_state_slugs_includes_dc(self):
        """Test that DC is included in valid slugs."""
        assert 'washington-dc' in VALID_STATE_SLUGS

    def test_state_slug_to_name_mapping(self):
        """Test slug to name mapping."""
        assert STATE_SLUG_TO_NAME['california'] == 'California'
        assert STATE_SLUG_TO_NAME['new-york'] == 'New York'
        assert STATE_SLUG_TO_NAME['washington-dc'] == 'District Of Columbia'

    def test_special_url_patterns(self):
        """Test special URL patterns for non-standard states."""
        assert 'north-carolina' in STATE_URL_PATTERNS
        assert STATE_URL_PATTERNS['north-carolina'] == '/stores/north-carolina/'
        assert 'washington-dc' in STATE_URL_PATTERNS
        assert STATE_URL_PATTERNS['washington-dc'] == '/stores/state/washington-dc/'

    def test_states_dict_consistency(self):
        """Test that _STATES dict is consistent with derived views."""
        # All slugs in VALID_STATE_SLUGS should be in _STATES
        for slug in VALID_STATE_SLUGS:
            assert slug in _STATES

        # All states in _STATES should be in VALID_STATE_SLUGS
        for slug in _STATES:
            assert slug in VALID_STATE_SLUGS

        # All slug-to-name mappings should match _STATES
        for slug, name in STATE_SLUG_TO_NAME.items():
            assert _STATES[slug].name == name

    def test_hyphenated_state_names(self):
        """Test hyphenated state names are properly mapped."""
        hyphenated_states = [
            ('new-hampshire', 'New Hampshire'),
            ('new-jersey', 'New Jersey'),
            ('new-mexico', 'New Mexico'),
            ('new-york', 'New York'),
            ('north-carolina', 'North Carolina'),
            ('north-dakota', 'North Dakota'),
            ('rhode-island', 'Rhode Island'),
            ('south-carolina', 'South Carolina'),
            ('south-dakota', 'South Dakota'),
            ('west-virginia', 'West Virginia'),
        ]
        for slug, name in hyphenated_states:
            assert slug in VALID_STATE_SLUGS
            assert STATE_SLUG_TO_NAME[slug] == name


class TestGetStateUrl:
    """Tests for get_state_url function."""

    def test_standard_state_url(self):
        """Test URL for standard state."""
        url = get_state_url('california')
        assert url == '/stores/state/california/'

    def test_north_carolina_special_url(self):
        """Test special URL for North Carolina."""
        url = get_state_url('north-carolina')
        assert url == '/stores/north-carolina/'

    def test_washington_dc_special_url(self):
        """Test special URL for Washington DC."""
        url = get_state_url('washington-dc')
        assert url == '/stores/state/washington-dc/'

    def test_unknown_state_defaults_to_standard(self):
        """Test that unknown state slug uses standard pattern."""
        url = get_state_url('unknown-state')
        assert url == '/stores/state/unknown-state/'

    def test_all_states_have_urls(self):
        """Test that all valid states return a URL."""
        for slug in VALID_STATE_SLUGS:
            url = get_state_url(slug)
            assert url.startswith('/stores/')
            assert url.endswith('/')
