"""
Tests for store_schema.py - Field naming standardization (Issue #170)
"""

import pytest
from src.shared.store_schema import (
    CANONICAL_FIELDS,
    FIELD_ALIASES,
    REQUIRED_STORE_FIELDS,
    RECOMMENDED_STORE_FIELDS,
    normalize_store_data,
    normalize_stores_batch,
)


class TestCanonicalFields:
    """Test canonical field definitions."""

    def test_required_fields_defined(self):
        """Verify all required fields are defined."""
        assert 'store_id' in REQUIRED_STORE_FIELDS
        assert 'name' in REQUIRED_STORE_FIELDS
        assert 'street_address' in REQUIRED_STORE_FIELDS
        assert 'city' in REQUIRED_STORE_FIELDS
        assert 'state' in REQUIRED_STORE_FIELDS

    def test_recommended_fields_separate_from_required(self):
        """Verify required and recommended fields are separate sets."""
        # Required and recommended should not overlap (per design in store_schema.py:94)
        assert REQUIRED_STORE_FIELDS.isdisjoint(RECOMMENDED_STORE_FIELDS)

    def test_recommended_fields_defined(self):
        """Verify recommended fields are defined."""
        assert 'zip' in RECOMMENDED_STORE_FIELDS
        assert 'phone' in RECOMMENDED_STORE_FIELDS
        assert 'latitude' in RECOMMENDED_STORE_FIELDS
        assert 'longitude' in RECOMMENDED_STORE_FIELDS
        assert 'url' in RECOMMENDED_STORE_FIELDS

    def test_canonical_fields_types(self):
        """Verify canonical field types are correct."""
        assert CANONICAL_FIELDS['store_id'] == str
        assert CANONICAL_FIELDS['name'] == str
        assert CANONICAL_FIELDS['zip'] == str
        assert CANONICAL_FIELDS['phone'] == str
        assert CANONICAL_FIELDS['latitude'] == float
        assert CANONICAL_FIELDS['longitude'] == float


class TestFieldAliases:
    """Test field alias mappings."""

    def test_postal_code_aliases(self):
        """Verify postal code field aliases."""
        assert FIELD_ALIASES['postal_code'] == 'zip'
        assert FIELD_ALIASES['zipcode'] == 'zip'
        assert FIELD_ALIASES['zip_code'] == 'zip'
        assert FIELD_ALIASES['postalcode'] == 'zip'

    def test_phone_aliases(self):
        """Verify phone number field aliases."""
        assert FIELD_ALIASES['phone_number'] == 'phone'
        assert FIELD_ALIASES['telephone'] == 'phone'
        assert FIELD_ALIASES['phoneNumber'] == 'phone'
        assert FIELD_ALIASES['tel'] == 'phone'

    def test_address_aliases(self):
        """Verify address field aliases."""
        assert FIELD_ALIASES['address'] == 'street_address'
        assert FIELD_ALIASES['street'] == 'street_address'
        assert FIELD_ALIASES['streetAddress'] == 'street_address'


class TestNormalizeStoreData:
    """Test single store normalization."""

    def test_normalize_postal_code(self):
        """Test normalization of postal_code to zip."""
        store = {
            'store_id': '123',
            'name': 'Test Store',
            'postal_code': '12345'
        }
        normalized = normalize_store_data(store)
        assert 'zip' in normalized
        assert normalized['zip'] == '12345'
        assert 'postal_code' not in normalized

    def test_normalize_phone_number(self):
        """Test normalization of phone_number to phone."""
        store = {
            'store_id': '123',
            'name': 'Test Store',
            'phone_number': '555-1234'
        }
        normalized = normalize_store_data(store)
        assert 'phone' in normalized
        assert normalized['phone'] == '555-1234'
        assert 'phone_number' not in normalized

    def test_normalize_telephone(self):
        """Test normalization of telephone to phone."""
        store = {
            'store_id': '456',
            'name': 'AT&T Store',
            'telephone': '555-5678'
        }
        normalized = normalize_store_data(store)
        assert 'phone' in normalized
        assert normalized['phone'] == '555-5678'
        assert 'telephone' not in normalized

    def test_normalize_multiple_fields(self):
        """Test normalization of multiple fields at once."""
        store = {
            'store_id': '789',
            'name': 'Multi Field Store',
            'postal_code': '67890',
            'phone_number': '555-9999',
            'street_address': '123 Main St'
        }
        normalized = normalize_store_data(store)
        assert normalized['zip'] == '67890'
        assert normalized['phone'] == '555-9999'
        assert normalized['street_address'] == '123 Main St'
        assert 'postal_code' not in normalized
        assert 'phone_number' not in normalized

    def test_canonical_name_takes_precedence(self):
        """Test that canonical field name takes precedence over alias."""
        store = {
            'store_id': '999',
            'zip': '11111',
            'postal_code': '22222'
        }
        normalized = normalize_store_data(store)
        # Canonical name should be preserved
        assert normalized['zip'] == '11111'
        assert 'postal_code' not in normalized

    def test_preserve_non_aliased_fields(self):
        """Test that non-aliased fields are preserved."""
        store = {
            'store_id': '111',
            'name': 'Test Store',
            'custom_field': 'custom_value',
            'latitude': 37.7749,
            'longitude': -122.4194
        }
        normalized = normalize_store_data(store)
        assert normalized['store_id'] == '111'
        assert normalized['name'] == 'Test Store'
        assert normalized['custom_field'] == 'custom_value'
        assert normalized['latitude'] == 37.7749
        assert normalized['longitude'] == -122.4194

    def test_add_retailer_metadata(self):
        """Test adding retailer metadata to normalized store."""
        store = {
            'store_id': '222',
            'name': 'Target Store',
            'postal_code': '55555'
        }
        normalized = normalize_store_data(store, retailer='target')
        assert normalized['retailer'] == 'target'
        assert normalized['zip'] == '55555'

    def test_preserve_existing_retailer(self):
        """Test that existing retailer field is not overwritten."""
        store = {
            'store_id': '333',
            'name': 'Store',
            'retailer': 'walmart'
        }
        normalized = normalize_store_data(store, retailer='target')
        # Original retailer should be preserved
        assert normalized['retailer'] == 'walmart'

    def test_normalize_empty_store(self):
        """Test normalizing an empty store dict."""
        store = {}
        normalized = normalize_store_data(store)
        assert normalized == {}

    def test_normalize_walmart_style_fields(self):
        """Test normalization of Walmart-style fields."""
        store = {
            'store_id': '1234',
            'name': 'Walmart Supercenter',
            'phone_number': '555-0000',
            'postal_code': '12345'
        }
        normalized = normalize_store_data(store, retailer='walmart')
        assert normalized['phone'] == '555-0000'
        assert normalized['zip'] == '12345'
        assert normalized['retailer'] == 'walmart'
        assert 'phone_number' not in normalized
        assert 'postal_code' not in normalized

    def test_normalize_target_style_fields(self):
        """Test normalization of Target-style fields (already canonical)."""
        store = {
            'store_id': 'T-1234',
            'name': 'Target Store',
            'phone': '555-1111',
            'zip': '54321'
        }
        normalized = normalize_store_data(store, retailer='target')
        # Should be unchanged except for retailer field
        assert normalized['phone'] == '555-1111'
        assert normalized['zip'] == '54321'
        assert normalized['retailer'] == 'target'

    def test_error_on_non_dict(self):
        """Test that normalize_store_data raises TypeError for non-dict input."""
        with pytest.raises(TypeError, match="Expected dict"):
            normalize_store_data("not a dict")

        with pytest.raises(TypeError, match="Expected dict"):
            normalize_store_data(None)

        with pytest.raises(TypeError, match="Expected dict"):
            normalize_store_data([])


class TestNormalizeStoresBatch:
    """Test batch store normalization."""

    def test_normalize_multiple_stores(self):
        """Test normalizing a batch of stores."""
        stores = [
            {'store_id': '1', 'postal_code': '11111', 'phone_number': '555-0001'},
            {'store_id': '2', 'postal_code': '22222', 'phone_number': '555-0002'},
            {'store_id': '3', 'postal_code': '33333', 'phone_number': '555-0003'}
        ]
        normalized = normalize_stores_batch(stores)
        assert len(normalized) == 3
        for i, store in enumerate(normalized, 1):
            assert f'{i}' in store['store_id']
            assert 'zip' in store
            assert 'phone' in store
            assert 'postal_code' not in store
            assert 'phone_number' not in store

    def test_normalize_batch_with_retailer(self):
        """Test normalizing a batch with retailer metadata."""
        stores = [
            {'store_id': '1', 'postal_code': '11111'},
            {'store_id': '2', 'postal_code': '22222'}
        ]
        normalized = normalize_stores_batch(stores, retailer='verizon')
        assert len(normalized) == 2
        for store in normalized:
            assert store['retailer'] == 'verizon'
            assert 'zip' in store

    def test_normalize_empty_batch(self):
        """Test normalizing an empty list."""
        normalized = normalize_stores_batch([])
        assert normalized == []

    def test_normalize_mixed_fields(self):
        """Test normalizing stores with different field combinations."""
        stores = [
            {'store_id': '1', 'postal_code': '11111'},  # Has postal_code
            {'store_id': '2', 'zip': '22222'},          # Already has zip
            {'store_id': '3', 'telephone': '555-0003'}, # Has telephone
            {'store_id': '4', 'phone': '555-0004'}      # Already has phone
        ]
        normalized = normalize_stores_batch(stores)
        assert normalized[0]['zip'] == '11111'
        assert normalized[1]['zip'] == '22222'
        assert normalized[2]['phone'] == '555-0003'
        assert normalized[3]['phone'] == '555-0004'

    def test_error_on_non_list(self):
        """Test that normalize_stores_batch raises TypeError for non-list input."""
        with pytest.raises(TypeError, match="Expected list"):
            normalize_stores_batch({'store_id': '1'})

        with pytest.raises(TypeError, match="Expected list"):
            normalize_stores_batch(None)


class TestRealWorldScenarios:
    """Test real-world retailer data normalization scenarios."""

    def test_att_store_normalization(self):
        """Test AT&T store with telephone and postal_code."""
        store = {
            'store_id': 'ATT-123',
            'name': 'AT&T Store',
            'telephone': '555-1234',
            'street_address': '123 Main St',
            'city': 'San Francisco',
            'state': 'CA',
            'postal_code': '94102',
            'country': 'US'
        }
        normalized = normalize_store_data(store, retailer='att')
        assert normalized['phone'] == '555-1234'
        assert normalized['zip'] == '94102'
        assert normalized['retailer'] == 'att'
        assert 'telephone' not in normalized
        assert 'postal_code' not in normalized

    def test_walmart_store_normalization(self):
        """Test Walmart store with phone_number and postal_code."""
        store = {
            'store_id': 'WM-5678',
            'name': 'Walmart Supercenter',
            'phone_number': '555-5678',
            'street_address': '456 Oak Ave',
            'city': 'Los Angeles',
            'state': 'CA',
            'postal_code': '90001',
            'country': 'US'
        }
        normalized = normalize_store_data(store, retailer='walmart')
        assert normalized['phone'] == '555-5678'
        assert normalized['zip'] == '90001'
        assert normalized['retailer'] == 'walmart'
        assert 'phone_number' not in normalized
        assert 'postal_code' not in normalized

    def test_verizon_store_normalization(self):
        """Test Verizon store with canonical fields (already normalized)."""
        store = {
            'store_id': 'VZ-9012',
            'name': 'Verizon Store',
            'phone': '555-9012',
            'street_address': '789 Pine St',
            'city': 'Seattle',
            'state': 'WA',
            'zip': '98101',
            'country': 'US'
        }
        normalized = normalize_store_data(store, retailer='verizon')
        # Should remain unchanged except for retailer
        assert normalized['phone'] == '555-9012'
        assert normalized['zip'] == '98101'
        assert normalized['retailer'] == 'verizon'

    def test_canadian_retailer_normalization(self):
        """Test Canadian retailer (Telus, Bell) with postal_code."""
        store = {
            'store_id': 'TELUS-001',
            'name': 'Telus Store',
            'phone': '604-555-1234',
            'street_address': '100 Main St',
            'city': 'Vancouver',
            'state': 'BC',
            'postal_code': 'V6B 2W9',
            'country': 'CA'
        }
        normalized = normalize_store_data(store, retailer='telus')
        assert normalized['zip'] == 'V6B 2W9'
        assert normalized['phone'] == '604-555-1234'
        assert 'postal_code' not in normalized

    def test_preserve_extra_retailer_fields(self):
        """Test that retailer-specific extra fields are preserved."""
        store = {
            'store_id': 'BEST-001',
            'name': 'Best Buy',
            'phone': '555-0000',
            'zip': '12345',
            'services': ['Geek Squad', 'In-Store Pickup'],
            'curbside_enabled': True,
            'hours': {'monday': '9-9', 'tuesday': '9-9'}
        }
        normalized = normalize_store_data(store, retailer='bestbuy')
        assert normalized['phone'] == '555-0000'
        assert normalized['zip'] == '12345'
        assert normalized['services'] == ['Geek Squad', 'In-Store Pickup']
        assert normalized['curbside_enabled'] is True
        assert normalized['hours'] == {'monday': '9-9', 'tuesday': '9-9'}


class TestValidationWithAliases:
    """Test validation handles field aliases correctly (Issue #215)."""

    def test_validate_postal_code_alias_no_warning(self):
        """Test that validation doesn't warn about missing 'zip' when 'postal_code' alias exists."""
        from src.shared.utils import validate_store_data

        store = {
            'store_id': 'TEST-001',
            'name': 'Test Store',
            'street_address': '123 Main St',
            'city': 'Seattle',
            'state': 'WA',
            'postal_code': '98101',  # Using alias instead of canonical 'zip'
            'phone': '555-1234',
            'latitude': 47.6062,
            'longitude': -122.3321,
            'url': 'https://example.com'
        }

        result = validate_store_data(store)
        # Should be valid
        assert result.is_valid
        # Should NOT warn about missing 'zip' since 'postal_code' is present
        assert all('zip' not in warning for warning in result.warnings)

    def test_validate_phone_number_alias_no_warning(self):
        """Test that validation doesn't warn about missing 'phone' when 'phone_number' alias exists."""
        from src.shared.utils import validate_store_data

        store = {
            'store_id': 'TEST-002',
            'name': 'Test Store 2',
            'street_address': '456 Oak Ave',
            'city': 'Portland',
            'state': 'OR',
            'zip': '97201',
            'phone_number': '555-5678',  # Using alias instead of canonical 'phone'
            'latitude': 45.5152,
            'longitude': -122.6784,
            'url': 'https://example.com'
        }

        result = validate_store_data(store)
        # Should be valid
        assert result.is_valid
        # Should NOT warn about missing 'phone' since 'phone_number' is present
        assert all('phone' not in warning for warning in result.warnings)

    def test_validate_telephone_alias_no_warning(self):
        """Test that validation doesn't warn about missing 'phone' when 'telephone' alias exists."""
        from src.shared.utils import validate_store_data

        store = {
            'store_id': 'ATT-123',
            'name': 'AT&T Store',
            'street_address': '789 Pine St',
            'city': 'Austin',
            'state': 'TX',
            'postal_code': '78701',
            'telephone': '555-9999',  # Using 'telephone' alias
            'latitude': 30.2672,
            'longitude': -97.7431,
            'url': 'https://example.com'
        }

        result = validate_store_data(store)
        assert result.is_valid
        assert all('phone' not in warning for warning in result.warnings)

    def test_validate_missing_field_and_aliases(self):
        """Test that validation warns when neither canonical field nor aliases are present."""
        from src.shared.utils import validate_store_data

        store = {
            'store_id': 'TEST-003',
            'name': 'Test Store 3',
            'street_address': '321 Elm St',
            'city': 'Denver',
            'state': 'CO',
            # Missing both 'zip' and all its aliases
            'phone': '555-1111'
        }

        result = validate_store_data(store)
        # Should still be valid (zip is recommended, not required)
        assert result.is_valid
        # Should warn about missing 'zip'
        assert any('zip' in warning for warning in result.warnings)

    def test_validate_multiple_aliases_present(self):
        """Test validation with multiple recommended field aliases."""
        from src.shared.utils import validate_store_data

        store = {
            'store_id': 'MULTI-001',
            'name': 'Multi Alias Store',
            'street_address': '999 Test Blvd',
            'city': 'Boston',
            'state': 'MA',
            'postal_code': '02101',  # zip alias
            'phone_number': '555-0000',  # phone alias
            'latitude': 42.3601,
            'longitude': -71.0589,
            'url': 'https://example.com'
        }

        result = validate_store_data(store)
        assert result.is_valid
        # Should not warn about missing 'zip' or 'phone'
        assert all('zip' not in warning and 'phone' not in warning for warning in result.warnings)
