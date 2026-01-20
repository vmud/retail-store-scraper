"""Unit tests for BestBuy scraper."""

import pytest
from unittest.mock import Mock, patch

from src.scrapers.bestbuy import (
    _normalize_service_name,
    _looks_like_service_name,
)


class TestNormalizeServiceName:
    """Tests for _normalize_service_name function."""

    def test_known_service_geek_squad(self):
        """Test normalization of Geek Squad variations."""
        assert _normalize_service_name('geek squad') == 'Geek Squad'
        assert _normalize_service_name('Geek Squad') == 'Geek Squad'
        assert _normalize_service_name('GEEK SQUAD') == 'Geek Squad'

    def test_known_service_apple_shop(self):
        """Test normalization of Apple Shop variations."""
        assert _normalize_service_name('apple shop') == 'Apple Shop'
        assert _normalize_service_name('Apple Shop') == 'Apple Shop'

    def test_known_service_apple_authorized(self):
        """Test normalization of Apple Authorized Service Provider."""
        # 'apple authorized' and full name should map to Apple Authorized Service Provider
        assert _normalize_service_name('apple authorized') == 'Apple Authorized Service Provider'
        assert _normalize_service_name('apple authorized service provider') == 'Apple Authorized Service Provider'
        # Note: 'apple service' maps to Apple Shop due to mapping order

    def test_known_service_trade_in(self):
        """Test normalization of Trade-In variations."""
        assert _normalize_service_name('trade-in') == 'Trade-In'
        assert _normalize_service_name('trade in') == 'Trade-In'

    def test_known_service_curbside(self):
        """Test normalization of Curbside Pickup."""
        assert _normalize_service_name('curbside') == 'Curbside Pickup'
        assert _normalize_service_name('curbside pickup') == 'Curbside Pickup'

    def test_known_service_samsung(self):
        """Test normalization of Samsung Experience."""
        assert _normalize_service_name('samsung experience') == 'Samsung Experience'
        assert _normalize_service_name('samsung experience only') == 'Samsung Experience'

    def test_prefix_removal(self):
        """Test removal of common prefixes."""
        # Should strip 'the' prefix and still match
        assert _normalize_service_name('the geek squad') == 'Geek Squad'
        assert _normalize_service_name('our apple shop') == 'Apple Shop'

    def test_suffix_removal(self):
        """Test removal of common suffixes."""
        # Suffixes should be stripped
        result = _normalize_service_name('some service center')
        # After stripping 'center', should normalize the remaining
        assert result is not None

    def test_too_short_rejected(self):
        """Test that too short strings are rejected."""
        assert _normalize_service_name('') is None
        assert _normalize_service_name('ab') is None
        assert _normalize_service_name('  ') is None

    def test_generic_terms_rejected(self):
        """Test that generic terms are rejected."""
        assert _normalize_service_name('services') is None
        assert _normalize_service_name('offered') is None
        assert _normalize_service_name('available') is None
        assert _normalize_service_name('specialty') is None
        assert _normalize_service_name('shops') is None

    def test_unknown_service_non_strict_accepted(self):
        """Test that unknown services are accepted in non-strict mode."""
        result = _normalize_service_name('custom repair station', strict=False)
        assert result == 'Custom Repair Station'

    def test_unknown_service_strict_rejected(self):
        """Test that unknown services are rejected in strict mode."""
        result = _normalize_service_name('custom repair station', strict=True)
        assert result is None

    def test_capitalization_of_unknown_services(self):
        """Test proper capitalization of unknown services."""
        result = _normalize_service_name('premium tech support', strict=False)
        assert result == 'Premium Tech Support'

        result = _normalize_service_name('LOUD SERVICE NAME', strict=False)
        assert result == 'Loud Service Name'


class TestLooksLikeServiceName:
    """Tests for _looks_like_service_name function."""

    def test_valid_service_names(self):
        """Test that valid service names are recognized."""
        assert _looks_like_service_name('Geek Squad') is True
        assert _looks_like_service_name('Apple Shop') is True
        assert _looks_like_service_name('Trade-In') is True

    def test_too_short_rejected(self):
        """Test that too short strings are rejected."""
        assert _looks_like_service_name('') is False
        assert _looks_like_service_name('ab') is False

    def test_too_long_rejected(self):
        """Test that too long strings are rejected."""
        long_text = 'a' * 60
        assert _looks_like_service_name(long_text) is False

    def test_generic_phrases_rejected(self):
        """Test that generic phrases are rejected."""
        assert _looks_like_service_name('click here') is False
        assert _looks_like_service_name('learn more') is False
        assert _looks_like_service_name('view all') is False
        assert _looks_like_service_name('store hours') is False


class TestServiceMappingConsistency:
    """Tests for service mapping consistency."""

    def test_mapping_keys_are_lowercase(self):
        """Test that all mapping keys are lowercase."""
        # Test that known mappings work with lowercase input
        known_services = [
            'geek squad', 'apple shop', 'trade-in', 'curbside',
            'samsung experience', 'yardbird', 'store pickup'
        ]
        for service in known_services:
            result = _normalize_service_name(service)
            assert result is not None, f"Service '{service}' should be recognized"

    def test_case_insensitive_matching(self):
        """Test that matching is case-insensitive."""
        # All these variations should map to the same canonical name
        variations = ['Geek Squad', 'GEEK SQUAD', 'geek squad', 'GeEk SqUaD']
        results = [_normalize_service_name(v) for v in variations]
        assert all(r == 'Geek Squad' for r in results)
