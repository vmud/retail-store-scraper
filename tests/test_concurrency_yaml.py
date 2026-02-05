"""Tests for concurrency YAML configuration loading - Issue #153."""

import tempfile
import pytest
from pathlib import Path
from src.shared.utils import configure_concurrency_from_yaml
from src.shared.concurrency import GlobalConcurrencyManager


@pytest.fixture
def manager():
    """Create a fresh manager instance for testing."""
    mgr = GlobalConcurrencyManager()
    mgr.reset()
    yield mgr
    mgr.reset()


@pytest.fixture
def temp_yaml():
    """Create a temporary YAML file for testing."""
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yield temp_file.name
    Path(temp_file.name).unlink(missing_ok=True)


def test_load_basic_config(manager, temp_yaml):
    """Test loading basic concurrency configuration."""
    config_content = """
concurrency:
  global_max_workers: 15
  per_retailer_max:
    verizon: 7
    target: 5
  proxy_rate_limit: 12.0
"""
    with open(temp_yaml, 'w') as f:
        f.write(config_content)

    configure_concurrency_from_yaml(temp_yaml)

    assert manager.config.global_max_workers == 15
    assert manager._retailer_max_workers['verizon'] == 7
    assert manager._retailer_max_workers['target'] == 5
    assert manager.config.proxy_requests_per_second == 12.0


def test_load_partial_config(manager, temp_yaml):
    """Test loading config with only some fields."""
    config_content = """
concurrency:
  global_max_workers: 20
"""
    with open(temp_yaml, 'w') as f:
        f.write(config_content)

    configure_concurrency_from_yaml(temp_yaml)

    assert manager.config.global_max_workers == 20
    # Other fields should keep defaults
    assert manager.config.per_retailer_max == 5


def test_load_empty_per_retailer(manager, temp_yaml):
    """Test loading config with empty per_retailer_max."""
    config_content = """
concurrency:
  global_max_workers: 10
  per_retailer_max: {}
  proxy_rate_limit: 10.0
"""
    with open(temp_yaml, 'w') as f:
        f.write(config_content)

    configure_concurrency_from_yaml(temp_yaml)

    assert manager.config.global_max_workers == 10
    assert len(manager._retailer_max_workers) == 0


def test_missing_config_file(manager):
    """Test handling of missing config file."""
    # Should not raise exception, just use defaults
    configure_concurrency_from_yaml('/nonexistent/path/to/config.yaml')

    # Should still have default values
    assert manager.config.global_max_workers == 10


def test_invalid_yaml(manager, temp_yaml):
    """Test handling of invalid YAML syntax."""
    config_content = """
concurrency:
  global_max_workers: 15
  invalid syntax here: [unclosed bracket
"""
    with open(temp_yaml, 'w') as f:
        f.write(config_content)

    # Should not raise exception, just use defaults
    configure_concurrency_from_yaml(temp_yaml)

    # Should keep default values due to parse error
    assert manager.config.global_max_workers == 10


def test_missing_concurrency_section(manager, temp_yaml):
    """Test config file without concurrency section."""
    config_content = """
proxy:
  mode: direct
retailers:
  verizon:
    enabled: true
"""
    with open(temp_yaml, 'w') as f:
        f.write(config_content)

    configure_concurrency_from_yaml(temp_yaml)

    # Should use defaults
    assert manager.config.global_max_workers == 10


def test_load_from_actual_config_file(manager):
    """Test loading from actual retailers.yaml (integration test)."""
    config_path = 'config/retailers.yaml'
    if not Path(config_path).exists():
        pytest.skip("retailers.yaml not found")

    configure_concurrency_from_yaml(config_path)

    # Should have loaded values from actual config
    assert manager.config.global_max_workers == 10
    # Check at least one retailer is configured
    assert len(manager._retailer_max_workers) > 0
    assert manager.config.proxy_requests_per_second == 10.0


def test_reconfigure_from_yaml(manager, temp_yaml):
    """Test that reconfiguring from YAML updates existing settings."""
    # Initial config
    config1 = """
concurrency:
  global_max_workers: 10
  per_retailer_max:
    verizon: 5
"""
    with open(temp_yaml, 'w') as f:
        f.write(config1)

    configure_concurrency_from_yaml(temp_yaml)
    assert manager.config.global_max_workers == 10
    assert manager._retailer_max_workers['verizon'] == 5

    # Update config
    config2 = """
concurrency:
  global_max_workers: 20
  per_retailer_max:
    verizon: 10
    target: 7
"""
    with open(temp_yaml, 'w') as f:
        f.write(config2)

    configure_concurrency_from_yaml(temp_yaml)
    assert manager.config.global_max_workers == 20
    assert manager._retailer_max_workers['verizon'] == 10
    assert manager._retailer_max_workers['target'] == 7


def test_yaml_with_comments(manager, temp_yaml):
    """Test loading YAML with comments."""
    config_content = """
# Concurrency configuration
concurrency:
  # Maximum workers across all retailers
  global_max_workers: 12
  # Per-retailer limits
  per_retailer_max:
    verizon: 6  # Verizon can handle more
    target: 4   # Conservative for Target
  proxy_rate_limit: 8.0  # Requests per second
"""
    with open(temp_yaml, 'w') as f:
        f.write(config_content)

    configure_concurrency_from_yaml(temp_yaml)

    assert manager.config.global_max_workers == 12
    assert manager._retailer_max_workers['verizon'] == 6
    assert manager._retailer_max_workers['target'] == 4
    assert manager.config.proxy_requests_per_second == 8.0


def test_yaml_with_many_retailers(manager, temp_yaml):
    """Test loading config with many retailers."""
    config_content = """
concurrency:
  global_max_workers: 10
  per_retailer_max:
    verizon: 7
    att: 5
    target: 5
    tmobile: 5
    walmart: 3
    bestbuy: 5
    cricket: 5
    bell: 1
    telus: 3
  proxy_rate_limit: 10.0
"""
    with open(temp_yaml, 'w') as f:
        f.write(config_content)

    configure_concurrency_from_yaml(temp_yaml)

    assert manager.config.global_max_workers == 10
    assert len(manager._retailer_max_workers) == 9
    assert manager._retailer_max_workers['verizon'] == 7
    assert manager._retailer_max_workers['bell'] == 1


def test_zero_workers_config(manager, temp_yaml):
    """Test config with zero workers (edge case)."""
    config_content = """
concurrency:
  global_max_workers: 0
  per_retailer_max:
    verizon: 0
"""
    with open(temp_yaml, 'w') as f:
        f.write(config_content)

    configure_concurrency_from_yaml(temp_yaml)

    # Zero workers is technically valid (though impractical)
    assert manager.config.global_max_workers == 0


def test_large_workers_config(manager, temp_yaml):
    """Test config with very large worker counts."""
    config_content = """
concurrency:
  global_max_workers: 1000
  per_retailer_max:
    verizon: 500
"""
    with open(temp_yaml, 'w') as f:
        f.write(config_content)

    configure_concurrency_from_yaml(temp_yaml)

    assert manager.config.global_max_workers == 1000
    assert manager._retailer_max_workers['verizon'] == 500


def test_null_per_retailer_max(manager, temp_yaml):
    """Test config with null per_retailer_max (YAML key exists but value is null).

    This tests the fix for: 'Logging crashes when YAML has null per_retailer_max'
    When YAML has 'per_retailer_max:' with no value, dict.get() returns None
    (not the default {}) because the key exists. The logging code must handle this.
    """
    config_content = """
concurrency:
  global_max_workers: 15
  per_retailer_max:
  proxy_rate_limit: 10.0
"""
    with open(temp_yaml, 'w') as f:
        f.write(config_content)

    # Should not raise TypeError from len(None)
    configure_concurrency_from_yaml(temp_yaml)

    assert manager.config.global_max_workers == 15
    assert manager.config.proxy_requests_per_second == 10.0
    # per_retailer_max should not have been updated (empty dict passed as None)
    assert len(manager._retailer_max_workers) == 0


def test_explicit_null_per_retailer_max(manager, temp_yaml):
    """Test config with explicit null per_retailer_max."""
    config_content = """
concurrency:
  global_max_workers: 12
  per_retailer_max: null
  proxy_rate_limit: 8.0
"""
    with open(temp_yaml, 'w') as f:
        f.write(config_content)

    # Should not raise TypeError from len(None)
    configure_concurrency_from_yaml(temp_yaml)

    assert manager.config.global_max_workers == 12
    assert manager.config.proxy_requests_per_second == 8.0
