"""Tests for store_serializer module - central store schema and normalization"""

import json
import pytest
from datetime import datetime

from src.shared.store_serializer import (
    Store,
    StoreSerializer,
    normalize_store_dict,
    FIELD_ALIASES,
)


class TestFieldAliases:
    """Test field name alias mappings."""

    def test_postal_code_alias(self):
        """postal_code should map to zip."""
        assert FIELD_ALIASES['postal_code'] == 'zip'

    def test_phone_number_alias(self):
        """phone_number should map to phone."""
        assert FIELD_ALIASES['phone_number'] == 'phone'

    def test_address_alias(self):
        """address should map to street_address."""
        assert FIELD_ALIASES['address'] == 'street_address'

    def test_coordinate_aliases(self):
        """lat, lng, lon should map to latitude/longitude."""
        assert FIELD_ALIASES['lat'] == 'latitude'
        assert FIELD_ALIASES['lng'] == 'longitude'
        assert FIELD_ALIASES['lon'] == 'longitude'


class TestStoreDataclass:
    """Test Store dataclass creation and validation."""

    def test_store_with_required_fields_only(self):
        """Store can be created with just required fields."""
        store = Store(
            store_id='TEST001',
            name='Test Store',
            street_address='123 Main St',
            city='Springfield',
            state='IL'
        )
        assert store.store_id == 'TEST001'
        assert store.name == 'Test Store'
        assert store.state == 'IL'
        assert store.country == 'US'  # Default value

    def test_store_with_all_fields(self):
        """Store can be created with all optional fields."""
        store = Store(
            store_id='TEST002',
            name='Full Store',
            street_address='456 Oak Ave',
            city='Portland',
            state='OR',
            zip='97201',
            country='US',
            phone='503-555-1234',
            latitude=45.5152,
            longitude=-122.6784,
            url='https://example.com/stores/test002',
            hours='Mon-Fri 9-5',
            retailer='test_retailer',
            scraped_at='2026-02-04T12:00:00'
        )
        assert store.zip == '97201'
        assert store.phone == '503-555-1234'
        assert store.latitude == 45.5152
        assert store.retailer == 'test_retailer'

    def test_store_to_dict(self):
        """to_dict returns dictionary representation."""
        store = Store(
            store_id='TEST003',
            name='Dict Test',
            street_address='789 Pine St',
            city='Seattle',
            state='WA',
            zip='98101'
        )
        data = store.to_dict()
        assert data['store_id'] == 'TEST003'
        assert data['city'] == 'Seattle'
        assert data['zip'] == '98101'
        # None values should be excluded
        assert 'phone' not in data or data['phone'] is None

    def test_store_to_dict_with_extra_fields(self):
        """to_dict handles extra_fields correctly."""
        store = Store(
            store_id='TEST004',
            name='Extra Test',
            street_address='321 Elm St',
            city='Austin',
            state='TX',
            extra_fields={'custom_field': 'value', 'store_type': 'flagship'}
        )

        # Default: include extra fields in separate key
        data = store.to_dict()
        assert 'extra_fields' in data
        assert data['extra_fields']['custom_field'] == 'value'

        # Flatten: merge extra fields to top level
        flat_data = store.to_dict(flatten=True)
        assert 'custom_field' in flat_data
        assert flat_data['custom_field'] == 'value'
        assert 'extra_fields' not in flat_data


class TestStoreFromRaw:
    """Test Store.from_raw() factory method with field normalization."""

    def test_from_raw_with_standard_fields(self):
        """from_raw creates Store from standard field names."""
        raw = {
            'store_id': 'RAW001',
            'name': 'Raw Store',
            'street_address': '100 First St',
            'city': 'Boston',
            'state': 'MA',
            'zip': '02101',
            'phone': '617-555-0000'
        }
        store = Store.from_raw(raw, retailer='test')
        assert store.store_id == 'RAW001'
        assert store.zip == '02101'
        assert store.retailer == 'test'

    def test_from_raw_normalizes_postal_code(self):
        """from_raw converts postal_code to zip."""
        raw = {
            'store_id': 'RAW002',
            'name': 'Target Style',
            'street_address': '200 Second Ave',
            'city': 'Minneapolis',
            'state': 'MN',
            'postal_code': '55401'  # Should become 'zip'
        }
        store = Store.from_raw(raw)
        assert store.zip == '55401'
        # Original field name should not exist in schema
        data = store.to_dict()
        assert 'postal_code' not in data

    def test_from_raw_normalizes_phone_number(self):
        """from_raw converts phone_number to phone."""
        raw = {
            'store_id': 'RAW003',
            'name': 'Walmart',
            'street_address': '300 Third Blvd',
            'city': 'Bentonville',
            'state': 'AR',
            'phone_number': '479-555-9999'  # Should become 'phone'
        }
        store = Store.from_raw(raw)
        assert store.phone == '479-555-9999'

    def test_from_raw_normalizes_coordinates(self):
        """from_raw converts lat/lng/lon to latitude/longitude."""
        # Test lat/lng
        raw1 = {
            'store_id': 'RAW004',
            'name': 'Coord Test 1',
            'street_address': '400 Fourth St',
            'city': 'Denver',
            'state': 'CO',
            'lat': 39.7392,
            'lng': -104.9903
        }
        store1 = Store.from_raw(raw1)
        assert store1.latitude == 39.7392
        assert store1.longitude == -104.9903

        # Test lon as alternative to lng
        raw2 = {
            'store_id': 'RAW005',
            'name': 'Coord Test 2',
            'street_address': '500 Fifth Ave',
            'city': 'Phoenix',
            'state': 'AZ',
            'lat': 33.4484,
            'lon': -112.0740
        }
        store2 = Store.from_raw(raw2)
        assert store2.latitude == 33.4484
        assert store2.longitude == -112.0740

    def test_from_raw_normalizes_address(self):
        """from_raw converts address to street_address."""
        raw = {
            'store_id': 'RAW006',
            'name': 'Address Test',
            'address': '600 Sixth St',  # Should become 'street_address'
            'city': 'Chicago',
            'state': 'IL'
        }
        store = Store.from_raw(raw)
        assert store.street_address == '600 Sixth St'

    def test_from_raw_preserves_extra_fields(self):
        """from_raw stores non-schema fields in extra_fields."""
        raw = {
            'store_id': 'RAW007',
            'name': 'Extra Test',
            'street_address': '700 Seventh Ave',
            'city': 'Miami',
            'state': 'FL',
            'store_type': 'superstore',
            'services': ['pharmacy', 'optical'],
            'manager': 'John Doe'
        }
        store = Store.from_raw(raw)
        assert 'store_type' in store.extra_fields
        assert store.extra_fields['store_type'] == 'superstore'
        assert store.extra_fields['services'] == ['pharmacy', 'optical']

    def test_from_raw_sets_scraped_at(self):
        """from_raw sets scraped_at timestamp if not provided."""
        raw = {
            'store_id': 'RAW008',
            'name': 'Timestamp Test',
            'street_address': '800 Eighth Blvd',
            'city': 'Dallas',
            'state': 'TX'
        }
        store = Store.from_raw(raw)
        assert store.scraped_at is not None
        # Should be ISO format timestamp
        datetime.fromisoformat(store.scraped_at)  # Should not raise

    def test_from_raw_preserves_existing_scraped_at(self):
        """from_raw keeps existing scraped_at value."""
        timestamp = '2026-01-15T10:30:00'
        raw = {
            'store_id': 'RAW009',
            'name': 'Preserved Timestamp',
            'street_address': '900 Ninth St',
            'city': 'Houston',
            'state': 'TX',
            'scraped_at': timestamp
        }
        store = Store.from_raw(raw)
        assert store.scraped_at == timestamp

    def test_from_raw_requires_required_fields(self):
        """from_raw raises ValueError if required fields missing."""
        # Missing store_id
        raw = {
            'name': 'Incomplete',
            'street_address': '123 Test St',
            'city': 'Test City',
            'state': 'TC'
        }
        with pytest.raises(ValueError, match='Validation failed: Missing required field'):
            Store.from_raw(raw)

        # Missing name
        raw = {
            'store_id': 'TEST001',
            'street_address': '123 Test St',
            'city': 'Test City',
            'state': 'TC'
        }
        with pytest.raises(ValueError, match='Validation failed: Missing required field'):
            Store.from_raw(raw)


class TestStoreSerializer:
    """Test StoreSerializer for CSV/Excel export."""

    def test_to_csv_row_basic(self):
        """to_csv_row converts Store to CSV-safe dictionary."""
        store = Store(
            store_id='CSV001',
            name='CSV Test Store',
            street_address='123 CSV St',
            city='Spreadsheet City',
            state='SS',
            zip='12345',
            phone='555-0123'
        )
        row = StoreSerializer.to_csv_row(store)
        assert row['store_id'] == 'CSV001'
        assert row['name'] == 'CSV Test Store'
        assert row['zip'] == '12345'
        assert isinstance(row['phone'], str)

    def test_to_csv_row_handles_none_values(self):
        """to_csv_row converts None to empty string."""
        store = Store(
            store_id='CSV002',
            name='Minimal Store',
            street_address='456 Minimal Ave',
            city='Bare',
            state='BN'
        )
        row = StoreSerializer.to_csv_row(store)
        # Optional fields should be empty strings
        assert row.get('phone', '') == ''
        assert row.get('zip', '') == ''

    def test_to_csv_row_sanitizes_values(self):
        """to_csv_row applies CSV formula injection protection."""
        store = Store(
            store_id='=DANGEROUS',  # Leading = could trigger formula
            name='Normal Name',
            street_address='+FORMULA',  # Leading + is dangerous
            city='Safe City',
            state='SC'
        )
        row = StoreSerializer.to_csv_row(store)
        # Dangerous values should be prefixed with quote
        assert row['store_id'].startswith("'")
        assert row['street_address'].startswith("'")

    def test_to_csv_row_preserves_negative_numbers(self):
        """to_csv_row doesn't sanitize negative coordinates."""
        store = Store(
            store_id='CSV003',
            name='Coordinate Store',
            street_address='789 Coord Ln',
            city='GeoCity',
            state='GC',
            latitude=45.5,
            longitude=-122.6  # Negative longitude
        )
        row = StoreSerializer.to_csv_row(store)
        # Negative number should not be prefixed with quote
        assert not row['longitude'].startswith("'")
        assert row['longitude'] == '-122.6'

    def test_to_csv_row_serializes_complex_types(self):
        """to_csv_row converts lists/dicts to JSON strings."""
        store = Store(
            store_id='CSV004',
            name='Complex Store',
            street_address='321 Complex Rd',
            city='DataCity',
            state='DC',
            extra_fields={'services': ['pickup', 'delivery']}
        )
        row = StoreSerializer.to_csv_row(store)
        # Extra field should be JSON string
        assert 'services' in row
        services = json.loads(row['services'])
        assert services == ['pickup', 'delivery']

    def test_get_ordered_fields_standard_only(self):
        """get_ordered_fields returns standard fields in order."""
        stores = [
            Store(
                store_id='ORD001',
                name='Order Test 1',
                street_address='100 Order St',
                city='OrderCity',
                state='OC',
                zip='11111'
            ),
            Store(
                store_id='ORD002',
                name='Order Test 2',
                street_address='200 Order Ave',
                city='OrderCity',
                state='OC',
                phone='555-9999'
            )
        ]
        fields = StoreSerializer.get_ordered_fields(stores)

        # Should start with standard fields in FIELD_ORDER
        assert fields[0] == 'store_id'
        assert fields[1] == 'name'
        assert 'street_address' in fields
        assert 'city' in fields
        assert 'state' in fields

    def test_get_ordered_fields_with_extra(self):
        """get_ordered_fields appends extra fields alphabetically."""
        stores = [
            Store(
                store_id='ORD003',
                name='Extra Order Test',
                street_address='300 Extra Blvd',
                city='ExtraCity',
                state='EC',
                extra_fields={
                    'z_last': 'value1',
                    'a_first': 'value2',
                    'm_middle': 'value3'
                }
            )
        ]
        fields = StoreSerializer.get_ordered_fields(stores)

        # Standard fields should be at the beginning in FIELD_ORDER
        # Find where standard fields end (last standard field present in output)
        std_fields_in_output = [f for f in StoreSerializer.FIELD_ORDER if f in fields]
        std_end = fields.index(std_fields_in_output[-1]) + 1

        # Extra fields should be alphabetically sorted after standard fields
        extra_fields = fields[std_end:]
        assert extra_fields == ['a_first', 'm_middle', 'z_last']

    def test_get_ordered_fields_empty_list(self):
        """get_ordered_fields returns FIELD_ORDER for empty list."""
        fields = StoreSerializer.get_ordered_fields([])
        assert fields == StoreSerializer.FIELD_ORDER


class TestNormalizeStoreDict:
    """Test normalize_store_dict convenience function."""

    def test_normalize_store_dict_basic(self):
        """normalize_store_dict normalizes field names in dict."""
        raw = {
            'store_id': 'NORM001',
            'name': 'Normalize Test',
            'street_address': '123 Norm St',
            'city': 'NormCity',
            'state': 'NC',
            'postal_code': '99999'
        }
        normalized = normalize_store_dict(raw, retailer='test')
        assert normalized['zip'] == '99999'
        assert 'postal_code' not in normalized
        assert normalized['retailer'] == 'test'

    def test_normalize_store_dict_with_extra_fields(self):
        """normalize_store_dict flattens extra fields by default."""
        raw = {
            'store_id': 'NORM002',
            'name': 'Extra Normalize',
            'street_address': '456 Extra Ave',
            'city': 'ExtraCity',
            'state': 'EC',
            'custom_field': 'custom_value'
        }
        normalized = normalize_store_dict(raw)
        # Extra fields should be in top level (flatten=True by default)
        assert normalized['custom_field'] == 'custom_value'

    def test_normalize_store_dict_handles_invalid_data(self):
        """normalize_store_dict applies basic normalization if validation fails."""
        # Missing required fields
        raw = {
            'postal_code': '12345',
            'phone_number': '555-0000'
        }
        # Should not raise, but apply basic field normalization
        normalized = normalize_store_dict(raw)
        assert normalized['zip'] == '12345'
        assert normalized['phone'] == '555-0000'


class TestIntegrationScenarios:
    """Test real-world usage scenarios."""

    def test_target_store_normalization(self):
        """Test normalization of Target-style data (postal_code)."""
        target_raw = {
            'store_id': 'T1234',
            'name': 'Target Store #1234',
            'street_address': '100 Target Way',
            'city': 'Minneapolis',
            'state': 'MN',
            'postal_code': '55403',  # Target uses postal_code
            'main_voice_phone_number': '612-555-1234',  # Non-standard
            'latitude': 44.9778,
            'longitude': -93.2650
        }
        store = Store.from_raw(target_raw, retailer='target')
        assert store.zip == '55403'
        # Non-standard phone field preserved in extra
        assert 'main_voice_phone_number' in store.extra_fields

    def test_walmart_store_normalization(self):
        """Test normalization of Walmart-style data (phone_number)."""
        walmart_raw = {
            'store_id': 'W5678',
            'name': 'Walmart Supercenter',
            'street_address': '200 Walmart Dr',
            'city': 'Bentonville',
            'state': 'AR',
            'postal_code': '72712',
            'phone_number': '479-555-5678',  # Walmart uses phone_number
        }
        store = Store.from_raw(walmart_raw, retailer='walmart')
        assert store.zip == '72712'
        assert store.phone == '479-555-5678'

    def test_verizon_store_normalization(self):
        """Test normalization of Verizon-style data (already uses zip)."""
        verizon_raw = {
            'store_id': 'V9012',
            'name': 'Verizon Store',
            'street_address': '300 Verizon Pkwy',
            'city': 'New York',
            'state': 'NY',
            'zip': '10001',  # Already uses 'zip'
            'phone': '212-555-9012'  # Already uses 'phone'
        }
        store = Store.from_raw(verizon_raw, retailer='verizon')
        assert store.zip == '10001'
        assert store.phone == '212-555-9012'

    def test_csv_export_consistency(self):
        """Test that CSV export has consistent column order."""
        stores = [
            Store.from_raw({
                'store_id': 'EXP001',
                'name': 'Export Store 1',
                'street_address': '100 Export St',
                'city': 'ExportCity',
                'state': 'EC',
                'postal_code': '11111',
                'custom_field_1': 'value1'
            }, retailer='retailer1'),
            Store.from_raw({
                'store_id': 'EXP002',
                'name': 'Export Store 2',
                'street_address': '200 Export Ave',
                'city': 'ExportCity',
                'state': 'EC',
                'zip': '22222',
                'custom_field_2': 'value2'
            }, retailer='retailer2')
        ]

        # Get field order
        fields = StoreSerializer.get_ordered_fields(stores)

        # Standard fields should come first in defined order
        assert fields[0] == 'store_id'
        assert fields[1] == 'name'
        assert 'retailer' in fields[:14]  # Within standard fields

        # Custom fields should be at end, sorted
        assert 'custom_field_1' in fields
        assert 'custom_field_2' in fields
        custom_idx_1 = fields.index('custom_field_1')
        custom_idx_2 = fields.index('custom_field_2')
        assert custom_idx_1 < custom_idx_2  # Alphabetical order


class TestBugFixes:
    """Test specific bug fixes from PR #216 reviews."""

    def test_normalize_store_dict_uses_retailer_in_fallback(self):
        """Test fix for retailer parameter ignored in fallback normalization path.

        Issue: When Store.from_raw() raises ValueError, normalize_store_dict
        should still apply the retailer parameter to the fallback result.
        """
        # Data missing required fields (triggers fallback)
        raw = {
            'postal_code': '12345',
            'phone_number': '555-0000'
        }
        normalized = normalize_store_dict(raw, retailer='test_retailer')

        # Should have normalized field names
        assert normalized['zip'] == '12345'
        assert normalized['phone'] == '555-0000'

        # Should have retailer applied in fallback path
        assert normalized['retailer'] == 'test_retailer'

    def test_get_ordered_fields_returns_copy_for_empty_list(self):
        """Test fix for mutable class constant returned for empty stores list.

        Issue: get_ordered_fields([]) returned direct reference to FIELD_ORDER,
        allowing callers to corrupt the class constant.
        """
        fields1 = StoreSerializer.get_ordered_fields([])
        fields2 = StoreSerializer.get_ordered_fields([])

        # Should return equal lists
        assert fields1 == fields2

        # But they should be different objects (copies)
        assert fields1 is not fields2

        # Modifying one should not affect the other or the class constant
        fields1.append('custom_field')
        assert 'custom_field' not in fields2
        assert 'custom_field' not in StoreSerializer.FIELD_ORDER

    def test_field_alias_collision_warning(self, caplog):
        """Test fix for field alias collision causing silent data loss.

        Issue: When both 'postal_code' and 'zip' exist with different values,
        the function should warn about the collision.
        """
        import logging
        caplog.set_level(logging.WARNING)

        # Data with both alias and canonical field (different values)
        raw = {
            'store_id': 'TEST001',
            'name': 'Collision Test',
            'street_address': '123 Test St',
            'city': 'TestCity',
            'state': 'TC',
            'postal_code': '11111',  # Alias
            'zip': '22222'           # Canonical (should win)
        }

        store = Store.from_raw(raw)

        # Canonical value should be used
        assert store.zip == '22222'

        # Should have logged a warning
        assert any('Field alias collision' in record.message for record in caplog.records)

    def test_field_alias_no_warning_same_value(self, caplog):
        """Test that no warning is logged when alias and canonical have same value."""
        import logging
        caplog.set_level(logging.WARNING)

        # Data with both alias and canonical field (same value - harmless)
        raw = {
            'store_id': 'TEST002',
            'name': 'No Collision Test',
            'street_address': '456 Test Ave',
            'city': 'TestCity',
            'state': 'TC',
            'postal_code': '33333',  # Alias
            'zip': '33333'           # Canonical (same value)
        }

        store = Store.from_raw(raw)

        # Should work fine
        assert store.zip == '33333'

        # Should NOT have logged a warning (same value is harmless)
        assert not any('Field alias collision' in record.message for record in caplog.records)
