"""Tests for CLI argument validation."""

import sys
from argparse import Namespace
from pathlib import Path

# Add parent directory to path to import run module
sys.path.insert(0, str(Path(__file__).parent.parent))

from run import validate_cli_options


class TestCLIValidation:
    """Test CLI validation function."""

    def test_render_js_without_proxy_fails(self):
        """Test that --render-js without --proxy returns validation error."""
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
