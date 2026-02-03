"""Tests for setup_logging functionality."""
import logging
from logging.handlers import RotatingFileHandler
import tempfile
import os
import subprocess
import sys
import pytest

from src.shared.utils import setup_logging


class TestSetupLogging:
    """Tests for setup_logging idempotency."""

    def setup_method(self):
        """Clear handlers before each test."""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()

    def teardown_method(self):
        """Clean up handlers after each test."""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()

    def test_console_handler_not_duplicated_on_multiple_calls(self):
        """Calling setup_logging multiple times should not add duplicate console handlers.

        This test runs in a subprocess to avoid pytest's log capture interference.
        """
        # Run the test in a clean subprocess to avoid pytest handler interference
        test_code = '''
import logging
from logging.handlers import RotatingFileHandler
import tempfile
import os
import sys

# Clear all handlers
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
    handler.close()

from src.shared.utils import setup_logging

with tempfile.TemporaryDirectory() as tmpdir:
    log_file = os.path.join(tmpdir, "test.log")

    setup_logging(log_file)
    setup_logging(log_file)
    setup_logging(log_file)

    console_handlers = [
        h for h in root_logger.handlers
        if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
    ]

    if len(console_handlers) != 1:
        print(f"FAIL: Expected 1 console handler, got {len(console_handlers)}")
        sys.exit(1)
    print("PASS")
    sys.exit(0)
'''
        result = subprocess.run(
            [sys.executable, '-c', test_code],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        assert result.returncode == 0, f"Test failed: {result.stdout} {result.stderr}"

    def test_file_handler_not_duplicated_on_multiple_calls(self):
        """Calling setup_logging multiple times should not add duplicate file handlers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            setup_logging(log_file)
            setup_logging(log_file)
            setup_logging(log_file)

            root_logger = logging.getLogger()
            file_handlers = [
                h for h in root_logger.handlers
                if isinstance(h, RotatingFileHandler)
            ]

            assert len(file_handlers) == 1, f"Expected 1 file handler, got {len(file_handlers)}"
