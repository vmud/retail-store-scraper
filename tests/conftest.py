"""Pytest configuration and fixtures for scraper dashboard tests"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from dashboard.app import app as flask_app, limiter

# Configure app for testing at module load time
# This ensures rate limiting and CSRF are disabled for ALL tests
flask_app.config.update({
    'TESTING': True,
    'WTF_CSRF_ENABLED': False,  # Disable CSRF for testing
    'RATELIMIT_ENABLED': False,  # Disable rate limiting for tests (#93)
})


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter before each test to prevent cross-test interference."""
    limiter.reset()
    yield
    # Reset again after the test for good measure
    limiter.reset()


@pytest.fixture
def app():
    """Flask application fixture"""
    # Config already set at module level, just return the app
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
