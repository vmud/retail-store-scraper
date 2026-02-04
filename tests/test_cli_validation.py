"""Tests for CLI argument validation."""

import sys
from argparse import ArgumentTypeError, Namespace
from pathlib import Path
import pytest

# Add parent directory to path to import run module
sys.path.insert(0, str(Path(__file__).parent.parent))

from run import validate_cli_options, validate_states, VALID_STATE_ABBREVS


class TestCLIValidation:
    """Test CLI validation function."""

    def test_render_js_without_proxy_fails(self):
        """Test that --render-js without --proxy returns error."""
        args = Namespace(
            test=False,
            limit=None,
            render_js=True,
            proxy=None,  # No proxy specified
            exclude=[]
        )
        errors = validate_cli_options(args)
        assert len(errors) == 1
        assert '--render-js requires --proxy web_scraper_api' in errors[0]

    def test_render_js_with_wrong_proxy_fails(self):
        """Test that --render-js with non-web_scraper_api proxy returns error."""
        args = Namespace(
            test=False,
            limit=None,
            render_js=True,
            proxy='residential',  # Wrong proxy type
            exclude=[]
        )
        errors = validate_cli_options(args)
        assert len(errors) == 1
        assert '--render-js requires --proxy web_scraper_api' in errors[0]

    def test_render_js_with_correct_proxy_passes(self):
        """Test that --render-js with web_scraper_api proxy passes validation."""
        args = Namespace(
            test=False,
            limit=None,
            render_js=True,
            proxy='web_scraper_api',  # Correct proxy type
            exclude=[]
        )
        errors = validate_cli_options(args)
        assert len(errors) == 0

    def test_render_js_false_without_proxy_passes(self):
        """Test that not using --render-js passes validation regardless of proxy."""
        args = Namespace(
            test=False,
            limit=None,
            render_js=False,
            proxy=None,
            exclude=[]
        )
        errors = validate_cli_options(args)
        assert len(errors) == 0

    def test_render_js_with_retailer_proxy_config_passes(self):
        """Test that retailer-specific web_scraper_api config allows --render-js."""
        args = Namespace(
            test=False,
            limit=None,
            render_js=True,
            proxy=None,
            exclude=[],
            retailer='verizon',
            all=False
        )
        config = {
            'proxy': {'mode': 'direct'},
            'retailers': {
                'verizon': {
                    'proxy': {'mode': 'web_scraper_api'}
                }
            }
        }
        errors = validate_cli_options(args, config)
        assert len(errors) == 0

    def test_test_and_limit_conflict(self):
        """Test that --test with --limit returns validation error."""
        args = Namespace(
            test=True,
            limit=100,
            render_js=False,
            proxy=None,
            exclude=[]
        )
        errors = validate_cli_options(args)
        assert len(errors) == 1
        assert 'Cannot use --test with --limit' in errors[0]

    def test_negative_limit_fails(self):
        """Test that negative --limit returns validation error."""
        args = Namespace(
            test=False,
            limit=-1,
            render_js=False,
            proxy=None,
            exclude=[]
        )
        errors = validate_cli_options(args)
        assert len(errors) == 1
        assert '--limit must be a positive integer' in errors[0]

    def test_exclude_without_all_fails(self):
        """Test that --exclude without --all returns validation error."""
        args = Namespace(
            test=False,
            limit=None,
            render_js=False,
            proxy=None,
            exclude=['verizon'],
            all=False
        )
        errors = validate_cli_options(args)
        assert len(errors) == 1
        assert '--exclude can only be used with --all' in errors[0]


class TestStateValidation:
    """Test state abbreviation validation for --states argument (#173)."""

    def test_valid_state_abbrevs_has_51_entries(self):
        """Test that VALID_STATE_ABBREVS contains all 50 states plus DC."""
        assert len(VALID_STATE_ABBREVS) == 51
        # Verify it includes DC
        assert 'DC' in VALID_STATE_ABBREVS
        # Verify it includes common states
        assert 'CA' in VALID_STATE_ABBREVS
        assert 'NY' in VALID_STATE_ABBREVS
        assert 'TX' in VALID_STATE_ABBREVS

    def test_validate_states_returns_list_for_valid_input(self):
        """Test that validate_states returns a list for valid state abbreviations."""
        result = validate_states('MD,PA,RI')
        assert isinstance(result, list)
        assert result == ['MD', 'PA', 'RI']

    def test_validate_states_normalizes_lowercase_to_uppercase(self):
        """Test that validate_states normalizes lowercase input to uppercase."""
        result = validate_states('md,pa,ri')
        assert result == ['MD', 'PA', 'RI']

    def test_validate_states_trims_whitespace(self):
        """Test that validate_states trims leading/trailing whitespace."""
        result = validate_states(' MD , PA , RI ')
        assert result == ['MD', 'PA', 'RI']

    def test_validate_states_returns_none_for_empty_input(self):
        """Test that validate_states returns None for empty string."""
        assert validate_states('') is None
        assert validate_states('   ') is None

    def test_validate_states_raises_error_for_invalid_states(self):
        """Test that validate_states raises ArgumentTypeError for invalid states."""
        with pytest.raises(ArgumentTypeError) as exc_info:
            validate_states('XX,YY')
        assert 'Invalid state abbreviation(s): XX, YY' in str(exc_info.value)

    def test_validate_states_lists_all_invalid_states_in_error(self):
        """Test that validate_states lists all invalid states in error message."""
        with pytest.raises(ArgumentTypeError) as exc_info:
            validate_states('MD,XX,PA,YY,ZZ')
        error_msg = str(exc_info.value)
        assert 'Invalid state abbreviation(s)' in error_msg
        # All invalid states should be in the error
        assert 'XX' in error_msg
        assert 'YY' in error_msg
        assert 'ZZ' in error_msg
        # Invalid states should be listed together
        assert 'XX, YY, ZZ' in error_msg

    def test_validate_states_accepts_all_51_valid_abbreviations(self):
        """Test that validate_states accepts all 51 valid state abbreviations."""
        all_states = ','.join(sorted(VALID_STATE_ABBREVS))
        result = validate_states(all_states)
        assert len(result) == 51
        assert set(result) == VALID_STATE_ABBREVS

    def test_validate_states_mixed_valid_and_invalid(self):
        """Test that validate_states only reports invalid states."""
        with pytest.raises(ArgumentTypeError) as exc_info:
            validate_states('CA,XX,NY')
        error_msg = str(exc_info.value)
        assert 'XX' in error_msg
        # Should provide helpful message
        assert 'Use standard 2-letter US state codes' in error_msg

    def test_validate_states_single_valid_state(self):
        """Test that validate_states works with a single valid state."""
        result = validate_states('CA')
        assert result == ['CA']

    def test_validate_states_single_invalid_state(self):
        """Test that validate_states rejects a single invalid state."""
        with pytest.raises(ArgumentTypeError) as exc_info:
            validate_states('ZZ')
        assert 'Invalid state abbreviation(s): ZZ' in str(exc_info.value)
