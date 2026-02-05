"""File I/O utilities for store data (DEPRECATED).

This module provides deprecated save functions that are maintained for
backwards compatibility. New code should use ExportService instead.

The functions in this module route through ExportService to avoid duplication.
"""

import logging
import warnings
from pathlib import Path
from typing import Any, Dict, List

__all__ = [
    'DEFAULT_CSV_FIELDNAMES',
    'save_to_csv',
    'save_to_json',
]

# Default fieldnames for backwards compatibility with original save_to_csv
# These are the original 11 fields used when no fieldnames were provided
DEFAULT_CSV_FIELDNAMES = [
    'name', 'street_address', 'city', 'state', 'zip',
    'country', 'latitude', 'longitude', 'phone', 'url', 'scraped_at'
]


def save_to_csv(stores: List[Dict[str, Any]], filepath: str, fieldnames: List[str] = None) -> None:
    """Save stores to CSV.

    DEPRECATED: Use ExportService.export_stores() instead.
    This function is maintained for backwards compatibility and routes through ExportService.

    Args:
        stores: List of store dictionaries
        filepath: Path to save CSV file
        fieldnames: Optional list of field names (uses default if not provided)
    """
    warnings.warn(
        "save_to_csv() is deprecated. Use ExportService.export_stores() instead.",
        DeprecationWarning,
        stacklevel=2
    )

    if not stores:
        logging.warning("No stores to save")
        return

    # Import here to avoid circular dependency
    from src.shared.export_service import ExportService, ExportFormat

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Route through ExportService to avoid duplication (#206)
    # Use provided fieldnames or fall back to default for backwards compatibility
    # Original save_to_csv used a fixed list of 11 fields when none provided
    # IMPORTANT: Check `is None` to preserve empty list behavior
    fields = fieldnames if fieldnames is not None else DEFAULT_CSV_FIELDNAMES
    retailer_config = {'output_fields': fields}
    ExportService.export_stores(stores, ExportFormat.CSV, str(path), retailer_config)


def save_to_json(stores: List[Dict[str, Any]], filepath: str) -> None:
    """Save stores to JSON.

    DEPRECATED: Use ExportService.export_stores() instead.
    This function is maintained for backwards compatibility and routes through ExportService.

    Args:
        stores: List of store dictionaries
        filepath: Path to save JSON file
    """
    warnings.warn(
        "save_to_json() is deprecated. Use ExportService.export_stores() instead.",
        DeprecationWarning,
        stacklevel=2
    )

    if not stores:
        logging.warning("No stores to save")
        return

    # Import here to avoid circular dependency
    from src.shared.export_service import ExportService, ExportFormat

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Route through ExportService to avoid duplication (#206)
    ExportService.export_stores(stores, ExportFormat.JSON, str(path))
