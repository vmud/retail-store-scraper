"""Pytest configuration and fixtures for scraper tests"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture
def mock_config_data():
    """Sample configuration data for testing"""
    return {
        'retailers': {
            'verizon': {
                'name': 'Verizon',
                'enabled': True,
                'base_url': 'https://www.verizon.com',
                'discovery_method': 'html_crawl',
                'min_delay': 1.0,
                'max_delay': 3.0,
                'timeout': 30,
                'checkpoint_interval': 50
            },
            'att': {
                'name': 'AT&T',
                'enabled': True,
                'base_url': 'https://www.att.com',
                'discovery_method': 'sitemap',
                'min_delay': 1.0,
                'max_delay': 3.0,
                'timeout': 30,
                'checkpoint_interval': 50
            }
        }
    }
