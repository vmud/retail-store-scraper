# Store Serializer Usage Guide

The store serializer module (`src/shared/store_serializer.py`) provides a central schema and normalization layer for store data across all retailers.

## Problem It Solves

Different scrapers use different field names for the same data:

| Retailer | ZIP/Postal | Phone | Coordinates |
|----------|-----------|-------|-------------|
| Target, AT&T, Bell, Telus, Walmart | `postal_code` | `phone` or `phone_number` | `latitude`, `longitude` |
| Verizon, T-Mobile, Cricket, Costco | `zip` | `phone` | `latitude`, `longitude` or `lat`, `lng` |

This leads to:
- Inconsistent CSV column names
- Manual remapping for data analysis
- Duplicated normalization logic

## Solution: Store Dataclass

A canonical data model with automatic field normalization:

```python
from src.shared import Store

# Target-style data (uses postal_code)
target_data = {
    'store_id': 'T1234',
    'name': 'Target Store #1234',
    'street_address': '100 Target Way',
    'city': 'Minneapolis',
    'state': 'MN',
    'postal_code': '55403',  # Non-standard
}

# Automatic normalization
store = Store.from_raw(target_data, retailer='target')
print(store.zip)  # '55403' (postal_code → zip)
```

## Core Components

### 1. Store Dataclass

Canonical schema with standard field names:

```python
@dataclass
class Store:
    # Required fields
    store_id: str
    name: str
    street_address: str
    city: str
    state: str

    # Optional fields
    zip: Optional[str] = None
    country: str = "US"
    phone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    url: Optional[str] = None
    hours: Optional[str] = None
    retailer: Optional[str] = None
    scraped_at: Optional[str] = None
    extra_fields: Dict[str, Any] = field(default_factory=dict)
```

### 2. Field Normalization

Automatic mapping of retailer-specific field names:

```python
FIELD_ALIASES = {
    'postal_code': 'zip',          # Target, AT&T, Bell, Telus, Walmart
    'phone_number': 'phone',       # Walmart
    'address': 'street_address',   # Generic
    'lat': 'latitude',             # Short form
    'lng': 'longitude',            # Short form
    'lon': 'longitude',            # Alternative short form
}
```

### 3. StoreSerializer

Ensures consistent CSV/Excel export:

```python
from src.shared import StoreSerializer

# Stable column ordering
FIELD_ORDER = [
    'store_id', 'name', 'street_address', 'city', 'state',
    'zip', 'country', 'phone', 'latitude', 'longitude',
    'url', 'hours', 'retailer', 'scraped_at'
]

# Extra fields appended alphabetically for determinism
```

## Usage Examples

### Basic Store Creation

```python
from src.shared import Store

# Create from normalized data
store = Store(
    store_id='TEST001',
    name='Test Store',
    street_address='123 Main St',
    city='Springfield',
    state='IL',
    zip='62701'
)
```

### Normalize Retailer Data

```python
from src.shared import Store

# Walmart data (uses phone_number, postal_code)
walmart_raw = {
    'store_id': 'W5678',
    'name': 'Walmart Supercenter',
    'street_address': '200 Walmart Dr',
    'city': 'Bentonville',
    'state': 'AR',
    'postal_code': '72712',      # → zip
    'phone_number': '479-555-5678'  # → phone
}

store = Store.from_raw(walmart_raw, retailer='walmart')
assert store.zip == '72712'
assert store.phone == '479-555-5678'
```

### Handle Extra Fields

Retailer-specific fields are preserved:

```python
target_raw = {
    'store_id': 'T1234',
    'name': 'Target Store',
    'street_address': '100 Target Way',
    'city': 'Minneapolis',
    'state': 'MN',
    'postal_code': '55403',
    'store_type': 'SuperTarget',       # Extra field
    'services': ['pharmacy', 'Starbucks']  # Extra field
}

store = Store.from_raw(target_raw, retailer='target')
print(store.extra_fields)
# {'store_type': 'SuperTarget', 'services': ['pharmacy', 'Starbucks']}

# Flatten extra fields to top level
data = store.to_dict(flatten=True)
print(data['store_type'])  # 'SuperTarget'
```

### CSV Export with Stable Columns

```python
from src.shared import Store, StoreSerializer

# Mix of retailers with different field names
raw_stores = [
    {'store_id': 'T1', 'name': 'Target', 'postal_code': '55403', ...},
    {'store_id': 'W1', 'name': 'Walmart', 'zip': '72712', ...},
    {'store_id': 'V1', 'name': 'Verizon', 'zip': '10001', ...}
]

# Normalize all stores
stores = [Store.from_raw(data, retailer=data['retailer']) for data in raw_stores]

# Get stable field ordering
fields = StoreSerializer.get_ordered_fields(stores)
# ['store_id', 'name', 'street_address', ..., 'zip', ...]
# Note: 'zip' is used for all stores, not 'postal_code'

# Generate CSV rows (with injection protection)
rows = [StoreSerializer.to_csv_row(store) for store in stores]

# Write to CSV
import csv
with open('stores.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
```

### Quick Dict Normalization

For legacy code that expects plain dictionaries:

```python
from src.shared import normalize_store_dict

# Normalize without creating Store object
raw = {
    'store_id': 'T1234',
    'postal_code': '55403',  # Will become 'zip'
    'phone_number': '612-555-1234'  # Will become 'phone'
}

normalized = normalize_store_dict(raw, retailer='target')
print(normalized['zip'])  # '55403'
print(normalized['phone'])  # '612-555-1234'
```

## Integration with Existing Scrapers

### Option 1: Keep Current Format (No Changes)

Scrapers can continue using their current field names. The Store schema is available when normalization is needed:

```python
# Scraper outputs dict as usual
def scrape_stores():
    return [
        {'store_id': '1', 'postal_code': '12345', ...},
        {'store_id': '2', 'postal_code': '67890', ...}
    ]

# Normalize before export
from src.shared import Store
stores = [Store.from_raw(s, retailer='target') for s in scrape_stores()]
```

### Option 2: Adopt Store Dataclass (Optional)

Scrapers can optionally return Store objects for type safety:

```python
from src.shared import Store

def scrape_stores():
    raw_data = fetch_api_data()
    # Normalize at source
    return [Store.from_raw(data, retailer='target') for data in raw_data]
```

Benefits:
- Type hints for IDE autocomplete
- Validation at scraper level
- No manual field mapping needed

## Field Reference

### Standard Fields (Always Normalized)

| Canonical Name | Aliases | Type | Required |
|---------------|---------|------|----------|
| `store_id` | - | str | ✅ |
| `name` | - | str | ✅ |
| `street_address` | `address` | str | ✅ |
| `city` | - | str | ✅ |
| `state` | - | str | ✅ |
| `zip` | `postal_code` | str | ❌ |
| `phone` | `phone_number` | str | ❌ |
| `latitude` | `lat` | float | ❌ |
| `longitude` | `lng`, `lon` | float | ❌ |
| `country` | - | str | ❌ (default: "US") |
| `url` | - | str | ❌ |
| `hours` | - | str | ❌ |
| `retailer` | - | str | ❌ |
| `scraped_at` | - | str | ❌ (auto-set) |

### Extra Fields

Non-standard fields are preserved in `extra_fields`:

```python
store = Store.from_raw({
    'store_id': '1',
    'name': 'Store',
    'street_address': '123 Main',
    'city': 'City',
    'state': 'ST',
    'custom_field': 'value',  # Extra
    'another_field': 123       # Extra
})

print(store.extra_fields)
# {'custom_field': 'value', 'another_field': 123}
```

## CSV Export Details

### Column Ordering

Columns appear in this order:
1. Standard fields (in `FIELD_ORDER`)
2. Extra fields (alphabetically sorted)

This ensures consistent ordering across:
- Different retailers
- Different scraper runs
- Different data sources

### CSV Injection Protection

`StoreSerializer.to_csv_row()` automatically applies `sanitize_csv_value()`:

```python
store = Store(
    store_id='=DANGEROUS',  # Leading = could trigger formula
    name='Normal Name',
    street_address='+FORMULA',  # Leading + is dangerous
    city='Safe City',
    state='SC'
)

row = StoreSerializer.to_csv_row(store)
# row['store_id'] == "'=DANGEROUS"  # Prefixed with quote
# row['street_address'] == "'+FORMULA"  # Prefixed with quote
```

Negative numbers (coordinates) are NOT sanitized:
```python
store.longitude = -122.4194  # Negative coordinate
row = StoreSerializer.to_csv_row(store)
# row['longitude'] == '-122.4194'  # NOT prefixed
```

## Testing

Run tests:
```bash
pytest tests/test_store_serializer.py -v
```

32 tests cover:
- Field alias mappings
- Store creation and validation
- Normalization of retailer-specific data
- CSV export and sanitization
- Field ordering consistency
- Integration scenarios

## API Reference

### Store

```python
@dataclass
class Store:
    """Canonical store schema with normalized field names."""

    @classmethod
    def from_raw(cls, data: Dict[str, Any], retailer: str = None) -> 'Store':
        """Create Store from raw scraper data with normalization.

        Args:
            data: Raw store data with retailer-specific field names
            retailer: Retailer name to set in store object

        Returns:
            Store object with normalized field names

        Raises:
            ValueError: If required fields are missing
        """

    def to_dict(self, include_extra: bool = True, flatten: bool = False) -> Dict[str, Any]:
        """Export to dictionary for serialization.

        Args:
            include_extra: Include extra_fields in output
            flatten: Merge extra_fields into top-level dict

        Returns:
            Dictionary with store data
        """
```

### StoreSerializer

```python
class StoreSerializer:
    """Handles CSV/Excel-safe serialization."""

    FIELD_ORDER = [
        'store_id', 'name', 'street_address', 'city', 'state',
        'zip', 'country', 'phone', 'latitude', 'longitude',
        'url', 'hours', 'retailer', 'scraped_at'
    ]

    @classmethod
    def to_csv_row(cls, store: Store) -> Dict[str, str]:
        """Convert store to CSV-safe row with sanitization.

        Args:
            store: Store object to serialize

        Returns:
            Dictionary with string values, sanitized for CSV
        """

    @classmethod
    def get_ordered_fields(cls, stores: List[Store]) -> List[str]:
        """Get ordered field list for CSV/Excel headers.

        Args:
            stores: List of Store objects

        Returns:
            Ordered list of field names (standard + extra)
        """
```

### normalize_store_dict

```python
def normalize_store_dict(data: Dict[str, Any], retailer: str = None) -> Dict[str, Any]:
    """Normalize a store dictionary without creating Store object.

    Convenience function for legacy code that expects plain dicts.

    Args:
        data: Raw store data dictionary
        retailer: Optional retailer name

    Returns:
        Dictionary with normalized field names
    """
```

## Backward Compatibility

- ✅ Existing scrapers work unchanged
- ✅ ExportService continues working as-is
- ✅ No breaking changes to current functionality
- ✅ Optional adoption by scrapers
- ✅ Can be used alongside existing patterns

## Future Enhancements

Possible future improvements:
- Schema versioning for backwards compatibility
- Validation rules per field (regex, ranges)
- Automatic geocoding for missing coordinates
- Address standardization (USPS format)
- Multi-language support for field names
