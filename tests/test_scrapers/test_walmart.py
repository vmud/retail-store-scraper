"""Unit tests for Walmart scraper."""

import json
import pytest
from unittest.mock import Mock, patch

from src.scrapers.walmart import (
    WalmartStore,
)


class TestWalmartStore:
    """Tests for WalmartStore dataclass."""

    def test_to_dict_basic(self):
        """Test basic dict conversion."""
        store = WalmartStore(
            store_id='1234',
            store_type='Supercenter',
            name='Walmart Supercenter',
            phone_number='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            postal_code='75001',
            country='US',
            latitude=32.7767,
            longitude=-96.7970,
            capabilities=['Pharmacy', 'Garden Center', 'Auto Care'],
            is_glass_eligible=True,
            url='https://www.walmart.com/store/1234',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['store_id'] == '1234'
        assert result['store_type'] == 'Supercenter'
        assert result['latitude'] == '32.7767'
        # Float to string conversion may drop trailing zeros
        assert result['longitude'] == '-96.797'
        assert json.loads(result['capabilities']) == ['Pharmacy', 'Garden Center', 'Auto Care']
        assert result['is_glass_eligible'] == 'True'

    def test_to_dict_none_coordinates(self):
        """Test dict conversion with None coordinates."""
        store = WalmartStore(
            store_id='1234',
            store_type='Supercenter',
            name='Walmart Supercenter',
            phone_number='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            postal_code='75001',
            country='US',
            latitude=None,
            longitude=None,
            capabilities=None,
            is_glass_eligible=False,
            url='https://www.walmart.com/store/1234',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['latitude'] == ''
        assert result['longitude'] == ''
        assert result['capabilities'] == ''
        assert result['is_glass_eligible'] == 'False'

    def test_to_dict_empty_capabilities(self):
        """Test dict conversion with empty capabilities list."""
        store = WalmartStore(
            store_id='1234',
            store_type='Neighborhood Market',
            name='Walmart Neighborhood Market',
            phone_number='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            postal_code='75001',
            country='US',
            latitude=32.7767,
            longitude=-96.7970,
            capabilities=[],
            is_glass_eligible=False,
            url='https://www.walmart.com/store/1234',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        # Empty list is kept as-is (falsy), not JSON encoded
        # This matches the `if result.get('capabilities'):` check
        assert result['capabilities'] == []

    def test_to_dict_single_capability(self):
        """Test dict conversion with single capability."""
        store = WalmartStore(
            store_id='5678',
            store_type='Supercenter',
            name='Walmart Supercenter',
            phone_number='(555) 987-6543',
            street_address='456 Oak Ave',
            city='Houston',
            state='TX',
            postal_code='77001',
            country='US',
            latitude=29.7604,
            longitude=-95.3698,
            capabilities=['Pharmacy'],
            is_glass_eligible=True,
            url='https://www.walmart.com/store/5678',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert json.loads(result['capabilities']) == ['Pharmacy']


class TestWalmartStoreTypes:
    """Tests for Walmart store type handling."""

    def test_supercenter_type(self):
        """Test Supercenter store type."""
        store = WalmartStore(
            store_id='1', store_type='Supercenter', name='Test',
            phone_number='', street_address='', city='', state='',
            postal_code='', country='', latitude=None, longitude=None,
            capabilities=None, is_glass_eligible=False, url='', scraped_at=''
        )
        assert store.store_type == 'Supercenter'

    def test_neighborhood_market_type(self):
        """Test Neighborhood Market store type."""
        store = WalmartStore(
            store_id='2', store_type='Neighborhood Market', name='Test',
            phone_number='', street_address='', city='', state='',
            postal_code='', country='', latitude=None, longitude=None,
            capabilities=None, is_glass_eligible=False, url='', scraped_at=''
        )
        assert store.store_type == 'Neighborhood Market'

    def test_sams_club_type(self):
        """Test Sam's Club store type."""
        store = WalmartStore(
            store_id='3', store_type="Sam's Club", name='Test',
            phone_number='', street_address='', city='', state='',
            postal_code='', country='', latitude=None, longitude=None,
            capabilities=None, is_glass_eligible=False, url='', scraped_at=''
        )
        assert store.store_type == "Sam's Club"
