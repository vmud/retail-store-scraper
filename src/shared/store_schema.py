"""
Store Schema - Canonical field definitions and normalization for store data.

This module defines the standardized field names and types for all retailer
store data, along with utilities to normalize retailer-specific field names
to the canonical schema.

Issue #170: Standardize field naming across retailers
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set


__all__ = [
    'CANONICAL_FIELDS',
    'FIELD_ALIASES',
    'RECOMMENDED_STORE_FIELDS',
    'REQUIRED_STORE_FIELDS',
    'CanonicalStoreSchema',
    'normalize_store_data',
    'normalize_stores_batch',
]


# =============================================================================
# CANONICAL FIELD DEFINITIONS
# =============================================================================

@dataclass(frozen=True)
class CanonicalStoreSchema:
    """Canonical field definitions for store data across all retailers.

    This schema defines the standard field names and types that all retailer
    data should be normalized to. Retailers may have additional custom fields,
    but core fields should use these standard names.

    Note: This class is currently used for documentation purposes and to define
    the canonical schema. It could be used in the future for:
    - Type hints and validation (e.g., validating stores against schema)
    - Generating TypedDict or Pydantic models
    - API documentation generation
    For now, normalization uses the CANONICAL_FIELDS dict and FIELD_ALIASES.
    """

    # Required fields - every store must have these
    store_id: str           # Unique identifier from retailer
    name: str              # Store name
    street_address: str    # Street address (without city/state/zip)
    city: str              # City name
    state: str             # State/province code (e.g., "CA", "ON")

    # Standardized field names (previously had aliases)
    zip: str = ''          # Postal/ZIP code (canonical name)
    phone: str = ''        # Phone number (canonical name)

    # Location data
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    country: str = ''

    # Additional metadata
    url: str = ''
    retailer: str = ''
    scraped_at: str = ''


# Canonical field names with their expected types
CANONICAL_FIELDS: Dict[str, type] = {
    'store_id': str,
    'name': str,
    'street_address': str,
    'city': str,
    'state': str,
    'zip': str,              # Standardized postal code field
    'phone': str,            # Standardized phone field
    'latitude': float,
    'longitude': float,
    'url': str,
    'retailer': str,
    'country': str,
    'scraped_at': str,
}

# Required fields that every store must have
REQUIRED_STORE_FIELDS: Set[str] = {
    'store_id',
    'name',
    'street_address',
    'city',
    'state',
}

# Recommended fields for complete store data (excluding required fields to avoid duplicate validation)
RECOMMENDED_STORE_FIELDS: Set[str] = {
    'zip',
    'phone',
    'latitude',
    'longitude',
    'url',
}

# Field aliases mapping retailer-specific names to canonical names
FIELD_ALIASES: Dict[str, str] = {
    # Postal code variations
    'postal_code': 'zip',
    'zipcode': 'zip',
    'zip_code': 'zip',
    'postalcode': 'zip',

    # Phone number variations
    'phone_number': 'phone',
    'telephone': 'phone',
    'phoneNumber': 'phone',
    'tel': 'phone',

    # Address variations (less common but possible)
    'address': 'street_address',
    'street': 'street_address',
    'address_line_1': 'street_address',
    'streetAddress': 'street_address',
}


# =============================================================================
# NORMALIZATION FUNCTIONS
# =============================================================================

def normalize_store_data(store: Dict[str, Any], retailer: str = None) -> Dict[str, Any]:
    """Normalize a single store's field names to the canonical schema.

    This function takes a store dictionary with retailer-specific field names
    and normalizes them to the canonical field names defined in FIELD_ALIASES.

    The normalization process:
    1. Creates a copy of the store data
    2. For each field alias, if the alias exists in the store:
       - Renames it to the canonical name
       - Removes the old alias field
    3. Adds retailer metadata if provided

    Args:
        store: Store dictionary with retailer-specific field names
        retailer: Optional retailer name to add as metadata

    Returns:
        Normalized store dictionary with canonical field names

    Examples:
        >>> store = {'store_id': '123', 'postal_code': '12345', 'phone_number': '555-1234'}
        >>> normalize_store_data(store)
        {'store_id': '123', 'zip': '12345', 'phone': '555-1234'}

        >>> store = {'store_id': '456', 'telephone': '555-5678', 'zipcode': '67890'}
        >>> normalize_store_data(store, retailer='target')
        {'store_id': '456', 'phone': '555-5678', 'zip': '67890', 'retailer': 'target'}
    """
    if not isinstance(store, dict):
        raise TypeError(f"Expected dict, got {type(store).__name__}")

    # Create a copy to avoid modifying the original
    normalized = store.copy()

    # Apply field aliases
    for alias, canonical in FIELD_ALIASES.items():
        if alias in normalized:
            value = normalized.pop(alias)
            # Only set canonical name if it doesn't already exist
            # (canonical name takes precedence if both exist)
            if canonical not in normalized:
                normalized[canonical] = value

    # Add retailer metadata if provided and not already present
    if retailer and 'retailer' not in normalized:
        normalized['retailer'] = retailer

    return normalized


def normalize_stores_batch(stores: List[Dict[str, Any]], retailer: str = None) -> List[Dict[str, Any]]:
    """Normalize field names for a batch of stores.

    Applies normalize_store_data() to each store in the list.

    Args:
        stores: List of store dictionaries
        retailer: Optional retailer name to add to all stores

    Returns:
        List of normalized store dictionaries

    Examples:
        >>> stores = [
        ...     {'store_id': '1', 'postal_code': '12345'},
        ...     {'store_id': '2', 'postal_code': '67890'}
        ... ]
        >>> normalize_stores_batch(stores, retailer='target')
        [
            {'store_id': '1', 'zip': '12345', 'retailer': 'target'},
            {'store_id': '2', 'zip': '67890', 'retailer': 'target'}
        ]
    """
    if not isinstance(stores, list):
        raise TypeError(f"Expected list, got {type(stores).__name__}")

    return [normalize_store_data(store, retailer=retailer) for store in stores]
