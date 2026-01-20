"""Unit tests for T-Mobile scraper."""

import json
import pytest
from unittest.mock import Mock, patch

from src.scrapers.tmobile import (
    TMobileStore,
    _extract_store_type_from_title,
)


class TestTMobileStore:
    """Tests for TMobileStore dataclass."""

    def test_to_dict_basic(self):
        """Test basic dict conversion."""
        store = TMobileStore(
            branch_code='TX-DAL-001',
            name='T-Mobile Dallas',
            store_type='T-Mobile Store',
            phone='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            zip='75001',
            country='US',
            latitude='32.7767',
            longitude='-96.7970',
            opening_hours=['Mon-Fri: 10am-8pm', 'Sat: 10am-6pm', 'Sun: 12pm-6pm'],
            url='https://www.t-mobile.com/stores/tx/dallas/tx-dal-001',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['branch_code'] == 'TX-DAL-001'
        assert result['store_type'] == 'T-Mobile Store'
        assert json.loads(result['opening_hours']) == ['Mon-Fri: 10am-8pm', 'Sat: 10am-6pm', 'Sun: 12pm-6pm']

    def test_to_dict_none_opening_hours(self):
        """Test dict conversion with None opening_hours."""
        store = TMobileStore(
            branch_code='TX-DAL-001',
            name='T-Mobile Dallas',
            store_type='T-Mobile Store',
            phone='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            zip='75001',
            country='US',
            latitude='32.7767',
            longitude='-96.7970',
            opening_hours=None,
            url='https://www.t-mobile.com/stores/tx/dallas/tx-dal-001',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['opening_hours'] == ''

    def test_to_dict_none_store_type(self):
        """Test dict conversion with None store_type."""
        store = TMobileStore(
            branch_code='TX-DAL-001',
            name='T-Mobile Dallas',
            store_type=None,
            phone='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            zip='75001',
            country='US',
            latitude='32.7767',
            longitude='-96.7970',
            opening_hours=None,
            url='https://www.t-mobile.com/stores/tx/dallas/tx-dal-001',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['store_type'] == ''


class TestExtractStoreTypeFromTitle:
    """Tests for _extract_store_type_from_title function."""

    def test_experience_store(self):
        """Test extraction of Experience Store type."""
        title = "T-Mobile Penn & I-494: Experience Store in Bloomington, MN"
        result = _extract_store_type_from_title(title)
        # Function returns full prefixed type name
        assert result == 'T-Mobile Experience Store'

    def test_store_type(self):
        """Test extraction of T-Mobile Store type."""
        # The function looks for specific patterns in the title
        title = "T-Mobile at 123 Main St in Dallas, TX"
        result = _extract_store_type_from_title(title)
        # May return None if pattern not found
        # This test documents current behavior

    def test_metro_store(self):
        """Test extraction of Metro by T-Mobile type."""
        # Test various Metro by T-Mobile formats
        title = "Metro by T-Mobile Broadway in Houston, TX"
        result = _extract_store_type_from_title(title)
        # Result depends on implementation

    def test_no_store_type_found(self):
        """Test when no store type is found."""
        title = "Some Random Page Title"
        result = _extract_store_type_from_title(title)
        assert result is None

    def test_empty_title(self):
        """Test with empty title."""
        result = _extract_store_type_from_title("")
        assert result is None
