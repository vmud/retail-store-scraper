"""Retailer scrapers registry"""

from pathlib import Path
from typing import Dict, List

import yaml

# Registry of available scrapers
SCRAPER_REGISTRY: Dict[str, str] = {
    'verizon': 'src.scrapers.verizon',
    'att': 'src.scrapers.att',
    'target': 'src.scrapers.target',
    'tmobile': 'src.scrapers.tmobile',
    'walmart': 'src.scrapers.walmart',
    'bestbuy': 'src.scrapers.bestbuy',
    'telus': 'src.scrapers.telus',
    'cricket': 'src.scrapers.cricket',
    'bell': 'src.scrapers.bell',
    'costco': 'src.scrapers.costco',
    'samsclub': 'src.scrapers.samsclub',
}


def get_available_retailers() -> List[str]:
    """Get list of all registered retailer names (enabled and disabled)"""
    return list(SCRAPER_REGISTRY.keys())


def get_enabled_retailers() -> List[str]:
    """Get list of enabled retailer names only.

    Reads the enabled field from config/retailers.yaml for each retailer.
    Retailers without an explicit enabled field default to True.
    """
    config_path = Path(__file__).parent.parent.parent / "config" / "retailers.yaml"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError):
        # Fall back to all registered retailers if config can't be read
        return list(SCRAPER_REGISTRY.keys())

    # Handle empty YAML files (safe_load returns None)
    config = config or {}

    retailers_config = config.get('retailers', {})
    return [
        name for name in SCRAPER_REGISTRY
        if retailers_config.get(name, {}).get('enabled', True)
    ]


def get_scraper_module(retailer: str):
    """Dynamically import and return a scraper module"""
    import importlib
    if retailer not in SCRAPER_REGISTRY:
        raise ValueError(f"Unknown retailer: {retailer}. Available: {get_available_retailers()}")
    return importlib.import_module(SCRAPER_REGISTRY[retailer])


__all__ = ['SCRAPER_REGISTRY', 'get_available_retailers', 'get_enabled_retailers', 'get_scraper_module']
