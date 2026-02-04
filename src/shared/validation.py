"""Store data validation utilities.

This module provides validation functions for ensuring scraped store data
meets quality standards and contains required fields.
"""

import logging
from typing import Any, Dict, List

from src.shared.constants import VALIDATION

__all__ = [
    'RECOMMENDED_STORE_FIELDS',
    'REQUIRED_STORE_FIELDS',
    'ValidationResult',
    'validate_store_data',
    'validate_stores_batch',
]


# Required fields that must be present and non-empty
REQUIRED_STORE_FIELDS = {'store_id', 'name', 'street_address', 'city', 'state'}

# Recommended fields that should be present for data quality
RECOMMENDED_STORE_FIELDS = {'latitude', 'longitude', 'phone', 'url'}


class ValidationResult:
    """Result of store data validation.

    Attributes:
        is_valid: True if validation passed (no errors)
        errors: List of error messages
        warnings: List of warning messages
    """

    def __init__(self, is_valid: bool, errors: List[str], warnings: List[str]):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings

    def __repr__(self) -> str:
        return f"ValidationResult(is_valid={self.is_valid}, errors={len(self.errors)}, warnings={len(self.warnings)})"


def validate_store_data(store: Dict[str, Any], strict: bool = False) -> ValidationResult:
    """Validate store data completeness and correctness.

    Args:
        store: Store data dictionary to validate
        strict: If True, treat missing recommended fields as errors

    Returns:
        ValidationResult with is_valid status, errors list, and warnings list
    """
    errors = []
    warnings = []

    # Check required fields
    for field in REQUIRED_STORE_FIELDS:
        value = store.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"Missing required field: {field}")

    # Check recommended fields
    for field in RECOMMENDED_STORE_FIELDS:
        if store.get(field) is None:
            if strict:
                errors.append(f"Missing recommended field: {field}")
            else:
                warnings.append(f"Missing recommended field: {field}")

    # Validate coordinates if present
    lat, lng = store.get('latitude'), store.get('longitude')
    if lat is not None and lng is not None:
        try:
            lat_float = float(lat)
            lng_float = float(lng)
            if not (VALIDATION.LAT_MIN <= lat_float <= VALIDATION.LAT_MAX):
                errors.append(f"Invalid latitude: {lat} (must be between {VALIDATION.LAT_MIN} and {VALIDATION.LAT_MAX})")
            if not (VALIDATION.LON_MIN <= lng_float <= VALIDATION.LON_MAX):
                errors.append(f"Invalid longitude: {lng} (must be between {VALIDATION.LON_MIN} and {VALIDATION.LON_MAX})")
        except (ValueError, TypeError):
            errors.append(f"Invalid coordinate format: lat={lat}, lng={lng}")

    # Validate postal code format (US 5-digit or 9-digit)
    postal_code = store.get('postal_code') or store.get('zip_code')
    if postal_code:
        postal_str = str(postal_code).strip()
        if postal_str and not (len(postal_str) == VALIDATION.ZIP_LENGTH_SHORT or len(postal_str) == VALIDATION.ZIP_LENGTH_LONG):
            # ZIP_LENGTH_LONG (10) for "12345-6789" format
            warnings.append(f"Unusual postal code format: {postal_code}")

    return ValidationResult(len(errors) == 0, errors, warnings)


def validate_stores_batch(
    stores: List[Dict[str, Any]],
    strict: bool = False,
    log_issues: bool = True
) -> Dict[str, Any]:
    """Validate a batch of stores and return summary.

    Args:
        stores: List of store data dictionaries
        strict: If True, treat missing recommended fields as errors
        log_issues: If True, log validation issues

    Returns:
        Dictionary with validation summary including:
        - total: Total number of stores
        - valid: Number of valid stores
        - invalid: Number of invalid stores
        - invalid_store_ids: List of invalid store IDs
        - error_count: Total number of errors
        - warning_count: Total number of warnings
    """
    total = len(stores)
    valid_count = 0
    invalid_stores = []
    all_errors = []
    all_warnings = []

    for i, store in enumerate(stores):
        result = validate_store_data(store, strict=strict)
        if result.is_valid:
            valid_count += 1
        else:
            store_id = store.get('store_id', f'index_{i}')
            invalid_stores.append(store_id)
            all_errors.extend([f"Store {store_id}: {e}" for e in result.errors])

        all_warnings.extend(result.warnings)

    if log_issues:
        if all_errors:
            for error in all_errors[:VALIDATION.ERROR_LOG_LIMIT]:
                logging.warning(error)
            if len(all_errors) > VALIDATION.ERROR_LOG_LIMIT:
                logging.warning(f"... and {len(all_errors) - VALIDATION.ERROR_LOG_LIMIT} more validation errors")

    return {
        'total': total,
        'valid': valid_count,
        'invalid': total - valid_count,
        'invalid_store_ids': invalid_stores,
        'error_count': len(all_errors),
        'warning_count': len(all_warnings),
    }
