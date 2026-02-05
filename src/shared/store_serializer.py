"""
Store Schema and Serializer - Central data model for all retailers.

Provides canonical field names and normalization to ensure consistent
field naming across scrapers and export formats.
"""

import json
import logging
from dataclasses import dataclass, asdict, field as dataclass_field
from datetime import datetime
from typing import Optional, Dict, Any, List

from src.shared.export_service import sanitize_csv_value
from src.shared.utils import validate_store_data


__all__ = [
    'Store',
    'StoreSerializer',
    'normalize_store_dict',
]


# Field name aliases for normalization
# Maps retailer-specific names to canonical names
FIELD_ALIASES = {
    'postal_code': 'zip',
    'phone_number': 'phone',
    'address': 'street_address',
    'lat': 'latitude',
    'lng': 'longitude',
    'lon': 'longitude',
}


@dataclass
class Store:
    """Canonical store schema with normalized field names.

    This dataclass defines the standard field names used across all retailers.
    Use Store.from_raw() to convert retailer-specific data to this schema.

    Required fields:
        store_id: Unique identifier for the store
        name: Store name
        street_address: Street address
        city: City name
        state: State/province code

    Optional fields:
        zip: Postal/ZIP code
        country: Country code (defaults to US)
        phone: Phone number
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        url: Store detail page URL
        hours: Operating hours
        retailer: Retailer name
        scraped_at: Timestamp when data was collected
    """
    # Required fields
    store_id: str
    name: str
    street_address: str
    city: str
    state: str

    # Optional fields with defaults
    zip: Optional[str] = None
    country: str = "US"
    phone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    url: Optional[str] = None
    hours: Optional[str] = None
    retailer: Optional[str] = None
    scraped_at: Optional[str] = None

    # Additional optional fields (retailer-specific extensions)
    # These preserve extra data without breaking the schema
    extra_fields: Optional[Dict[str, Any]] = dataclass_field(default_factory=dict)

    @classmethod
    def from_raw(cls, data: Dict[str, Any], retailer: str = None) -> 'Store':
        """Create Store from raw scraper data with field normalization.

        Handles various field name variations:
        - postal_code → zip
        - phone_number → phone
        - address → street_address
        - lat/lng/lon → latitude/longitude

        Args:
            data: Raw store data dictionary from scraper
            retailer: Retailer name to set in store object

        Returns:
            Store object with normalized field names

        Raises:
            ValueError: If required fields are missing
        """
        # Apply field aliases
        normalized = cls._normalize_fields(data)

        # Set retailer if provided
        if retailer:
            normalized['retailer'] = retailer

        # Set scraped_at timestamp if not present
        if 'scraped_at' not in normalized or not normalized['scraped_at']:
            normalized['scraped_at'] = datetime.now().isoformat()

        # Extract fields that belong to the Store schema (derived from dataclass)
        store_fields = {f for f in cls.__dataclass_fields__ if f != 'extra_fields'}

        # Separate schema fields from extra fields
        store_data = {}
        extra = {}
        for key, value in normalized.items():
            if key in store_fields:
                store_data[key] = value
            else:
                extra[key] = value

        # Store extra fields in extra_fields dict
        if extra:
            store_data['extra_fields'] = extra

        # Validate required fields using shared validation
        validation_result = validate_store_data(store_data)
        if not validation_result.is_valid:
            raise ValueError(f"Validation failed: {', '.join(validation_result.errors)}")

        return cls(**store_data)

    @staticmethod
    def _normalize_fields(data: Dict[str, Any]) -> Dict[str, Any]:
        """Map retailer-specific field names to canonical names.

        Detects and warns about field alias collisions where both the aliased
        field and canonical field exist in input data (e.g., both 'postal_code'
        and 'zip'). The canonical field value takes precedence.

        Args:
            data: Raw store data with potentially non-standard field names

        Returns:
            Dictionary with normalized field names
        """
        # First pass: detect collisions
        canonical_mapping = {}  # Maps canonical keys to list of (source_key, value)
        for key, value in data.items():
            canonical_key = FIELD_ALIASES.get(key, key)
            if canonical_key not in canonical_mapping:
                canonical_mapping[canonical_key] = []
            canonical_mapping[canonical_key].append((key, value))

        # Second pass: build result and warn on collisions
        result = {}
        for canonical_key, sources in canonical_mapping.items():
            if len(sources) > 1:
                # Collision detected - multiple sources for same canonical field
                # Check if values differ
                values = [value for _, value in sources]
                if len(set(str(v) for v in values)) > 1:  # Different values
                    # Identify alias sources for warning message
                    alias_sources = [key for key, _ in sources if key != canonical_key]

                    logging.warning(
                        f"Field alias collision: both {alias_sources} and canonical "
                        f"field '{canonical_key}' exist with different values. "
                        f"Canonical value will be used."
                    )

            # Use the canonical field's value if present, otherwise first source
            canonical_value = next(
                (value for key, value in sources if key == canonical_key),
                sources[0][1]  # Fallback to first source if no canonical field
            )
            result[canonical_key] = canonical_value

        return result

    def to_dict(self, include_extra: bool = True, flatten: bool = False, for_csv: bool = False) -> Dict[str, Any]:
        """Export to dictionary for serialization.

        Args:
            include_extra: Include extra_fields in output
            flatten: Flatten extra_fields into top-level dict
            for_csv: If True, preserve None values (converted to empty strings by caller)

        Returns:
            Dictionary with store data
        """
        data = asdict(self)

        # Remove None values to reduce output size (unless preparing for CSV)
        if not for_csv:
            data = {k: v for k, v in data.items() if v is not None}

        # Handle extra_fields
        extra = data.pop('extra_fields', {})
        if include_extra and extra:
            if flatten:
                # Merge extra fields into top level
                data.update(extra)
            else:
                # Keep as nested dict
                data['extra_fields'] = extra

        return data


class StoreSerializer:
    """Handles CSV/Excel-safe serialization with consistent field ordering.

    Provides stable column ordering for CSV/Excel exports and applies
    sanitization to prevent formula injection attacks.
    """

    # Standard field order for CSV/Excel exports
    # This ensures consistent column ordering across all retailers
    FIELD_ORDER = [
        'store_id',
        'name',
        'street_address',
        'city',
        'state',
        'zip',
        'country',
        'phone',
        'latitude',
        'longitude',
        'url',
        'hours',
        'retailer',
        'scraped_at',
    ]

    @classmethod
    def to_csv_row(cls, store: Store) -> Dict[str, str]:
        """Convert store to CSV-safe row with consistent field ordering.

        Applies sanitization to prevent CSV formula injection and ensures
        all values are strings suitable for CSV export.

        Args:
            store: Store object to serialize

        Returns:
            Dictionary with string values, sanitized for CSV
        """
        # Get base dict with None values preserved for CSV conversion
        data = store.to_dict(include_extra=True, flatten=True, for_csv=True)

        # Convert all values to strings and sanitize
        csv_row = {}
        for key, value in data.items():
            # Convert to string
            if value is None:
                str_value = ''
            elif isinstance(value, (list, dict)):
                # JSON serialize complex types
                str_value = json.dumps(value)
            else:
                str_value = str(value)

            # Apply CSV sanitization
            csv_row[key] = sanitize_csv_value(str_value)

        return csv_row

    @classmethod
    def get_ordered_fields(cls, stores: List[Store]) -> List[str]:
        """Get ordered field list for CSV/Excel headers.

        Uses FIELD_ORDER for standard fields, then appends any extra fields
        found in the stores (alphabetically sorted for determinism).

        Args:
            stores: List of Store objects

        Returns:
            Ordered list of field names
        """
        if not stores:
            return list(cls.FIELD_ORDER)

        # Collect all fields from stores
        all_fields = set()
        for store in stores:
            data = store.to_dict(include_extra=True, flatten=True, for_csv=True)
            all_fields.update(data.keys())

        # Start with standard fields (in order)
        ordered = [f for f in cls.FIELD_ORDER if f in all_fields]

        # Append extra fields (sorted for determinism)
        extra_fields = sorted(all_fields - set(cls.FIELD_ORDER))
        ordered.extend(extra_fields)

        return ordered


def normalize_store_dict(data: Dict[str, Any], retailer: str = None) -> Dict[str, Any]:
    """Normalize a store dictionary using Store schema and return a normalized copy.

    Convenience function for normalizing field names without creating
    a Store object. Useful for legacy code that expects plain dicts.

    Args:
        data: Raw store data dictionary
        retailer: Optional retailer name to add to data

    Returns:
        Dictionary with normalized field names
    """
    # Use Store for normalization but return as dict
    try:
        store = Store.from_raw(data, retailer=retailer)
        return store.to_dict(include_extra=True, flatten=True)
    except ValueError as e:
        # If missing required fields, do basic normalization
        logging.warning(f"Cannot create Store from data, applying basic normalization: {e}")
        normalized = Store._normalize_fields(data)
        # Apply retailer to fallback path as well
        if retailer:
            normalized['retailer'] = retailer
        return normalized
