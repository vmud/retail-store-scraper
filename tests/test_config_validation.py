"""Tests for config validation in run.py."""

import sys
import tempfile
from pathlib import Path

import yaml

# Add parent directory to path to import run module
sys.path.insert(0, str(Path(__file__).parent.parent))

from run import validate_config_on_startup


class TestConfigValidation:
    """Test config validation function."""

    def test_non_numeric_delays_dont_crash_validation(self):
        """Test that non-numeric min_delay/max_delay values don't cause TypeError.
        
        This tests the fix for the issue where validation would crash when trying
        to compare non-numeric delay values at line 106, instead of properly
        collecting and returning validation errors.
        """
        # Create a config with non-numeric delay values
        config = {
            'retailers': {
                'test_retailer': {
                    'base_url': 'https://example.com',
                    'min_delay': 'not_a_number',  # Invalid
                    'max_delay': 'also_not_a_number'  # Invalid
                }
            }
        }

        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name

        try:
            # Validation should complete without crashing
            errors = validate_config_on_startup(config_path)
            
            # Should have errors for both non-numeric fields
            assert len(errors) >= 2, f"Expected at least 2 errors, got {len(errors)}: {errors}"
            
            # Check that both delay fields are reported as invalid
            delay_errors = [e for e in errors if 'min_delay' in e or 'max_delay' in e]
            assert len(delay_errors) >= 2, f"Expected 2 delay errors, got {len(delay_errors)}: {delay_errors}"
            
        finally:
            # Clean up temp file
            Path(config_path).unlink()

    def test_mixed_type_delays_dont_crash_validation(self):
        """Test that mixed-type delay values (string and number) don't cause TypeError."""
        config = {
            'retailers': {
                'test_retailer': {
                    'base_url': 'https://example.com',
                    'min_delay': 'five',  # Invalid string
                    'max_delay': 10  # Valid number
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name

        try:
            errors = validate_config_on_startup(config_path)
            
            # Should have at least 1 error for min_delay
            assert len(errors) >= 1
            assert any('min_delay' in e for e in errors)
            
        finally:
            Path(config_path).unlink()

    def test_valid_delays_with_correct_order_passes(self):
        """Test that valid numeric delays in correct order pass validation."""
        config = {
            'retailers': {
                'test_retailer': {
                    'enabled': True,
                    'base_url': 'https://example.com',
                    'min_delay': 2.0,
                    'max_delay': 5.0
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name

        try:
            errors = validate_config_on_startup(config_path)
            
            # Should have no errors
            assert len(errors) == 0, f"Expected no errors, got: {errors}"
            
        finally:
            Path(config_path).unlink()

    def test_valid_delays_with_wrong_order_fails(self):
        """Test that valid numeric delays in wrong order are caught."""
        config = {
            'retailers': {
                'test_retailer': {
                    'base_url': 'https://example.com',
                    'min_delay': 10.0,  # Greater than max
                    'max_delay': 2.0
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name

        try:
            errors = validate_config_on_startup(config_path)
            
            # Should have error about delay order
            assert len(errors) >= 1
            assert any('cannot be greater than' in e for e in errors)
            
        finally:
            Path(config_path).unlink()

    def test_negative_delays_fail_validation(self):
        """Test that negative delay values fail validation."""
        config = {
            'retailers': {
                'test_retailer': {
                    'base_url': 'https://example.com',
                    'min_delay': -1.0,
                    'max_delay': -5.0
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name

        try:
            errors = validate_config_on_startup(config_path)
            
            # Should have errors for both negative values
            assert len(errors) >= 2
            negative_errors = [e for e in errors if 'non-negative' in e]
            assert len(negative_errors) >= 2
            
        finally:
            Path(config_path).unlink()
