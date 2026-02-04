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
    'save_to_csv',
    'save_to_json',
]


def save_to_csv(stores: List[Dict[str, Any]], filepath: str, fieldnames: List[str] = None) -> None:
    """Save stores to CSV.

    DEPRECATED: Use ExportService.export_csv() instead.
    This function is maintained for backwards compatibility and routes through ExportService.

    Args:
        stores: List of store dictionaries
        filepath: Path to save CSV file
        fieldnames: Optional list of field names (uses default if not provided)
    """
    warnings.warn(
        "save_to_csv() is deprecated. Use ExportService.export_csv() instead.",
        DeprecationWarning,
        stacklevel=2
    )

    if not stores:
        logging.warning("No stores to save")
        return

    # Import here to avoid circular dependency
    from src.shared.export_service import ExportService

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Route through ExportService to avoid duplication (#206)
    service = ExportService()
    service.export_csv(stores, str(path), fieldnames=fieldnames)

    logging.info(f"Saved {len(stores)} stores to CSV: {filepath}")


def save_to_json(stores: List[Dict[str, Any]], filepath: str) -> None:
    """Save stores to JSON.

    DEPRECATED: Use ExportService.export_json() instead.
    This function is maintained for backwards compatibility and routes through ExportService.

    Args:
        stores: List of store dictionaries
        filepath: Path to save JSON file
    """
    warnings.warn(
        "save_to_json() is deprecated. Use ExportService.export_json() instead.",
        DeprecationWarning,
        stacklevel=2
    )

    if not stores:
        logging.warning("No stores to save")
        return

    # Import here to avoid circular dependency
    from src.shared.export_service import ExportService

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Route through ExportService to avoid duplication (#206)
    service = ExportService()
    service.export_json(stores, str(path))

    logging.info(f"Saved {len(stores)} stores to JSON: {filepath}")
