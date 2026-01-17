"""Pytest configuration and fixtures for scraper dashboard tests"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from dashboard.app import app as flask_app


@pytest.fixture
def app():
    """Flask application fixture"""
    flask_app.config.update({
        'TESTING': True,
    })
    return flask_app


@pytest.fixture
def client(app):
    """Flask test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Flask test CLI runner"""
    return app.test_cli_runner()


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
