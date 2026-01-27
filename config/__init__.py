"""Configuration module for retailer scrapers"""

from typing import Dict, Any
import importlib

# Mapping of retailer names to their config modules
CONFIG_MODULES = {
    'verizon': 'config.verizon_config',
    'att': 'config.att_config',
    'target': 'config.target_config',
    'tmobile': 'config.tmobile_config',
    'walmart': 'config.walmart_config',
    'bestbuy': 'config.bestbuy_config',
    'telus': 'config.telus_config',
    'cricket': 'config.cricket_config',
}

def get_config(retailer: str):
    """Get configuration module for a retailer"""
    if retailer not in CONFIG_MODULES:
        raise ValueError(f"Unknown retailer: {retailer}")
    return importlib.import_module(CONFIG_MODULES[retailer])

__all__ = ['get_config', 'CONFIG_MODULES']
