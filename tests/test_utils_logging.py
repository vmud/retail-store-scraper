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

    def test_filehandler_not_confused_with_console_handler(self):
        """A plain FileHandler should not be confused with a console handler.

        This tests the fix for cursor[bot] review comment: FileHandler extends
        StreamHandler, so the console handler check must exclude FileHandler
        (not just RotatingFileHandler).
        """
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
    other_log = os.path.join(tmpdir, "other.log")

    # Add a plain FileHandler BEFORE calling setup_logging
    plain_file_handler = logging.FileHandler(other_log)
    root_logger.addHandler(plain_file_handler)

    # Now call setup_logging - it should still add a console handler
    # because FileHandler is NOT a console handler
    setup_logging(log_file)

    # Check we have: 1 plain FileHandler, 1 RotatingFileHandler, 1 console StreamHandler
    handlers_by_type = {}
    for h in root_logger.handlers:
        if isinstance(h, RotatingFileHandler):
            handlers_by_type.setdefault('rotating', []).append(h)
        elif isinstance(h, logging.FileHandler):
            handlers_by_type.setdefault('file', []).append(h)
        elif isinstance(h, logging.StreamHandler):
            handlers_by_type.setdefault('console', []).append(h)

    if len(handlers_by_type.get('console', [])) != 1:
        print(f"FAIL: Expected 1 console handler, got {len(handlers_by_type.get('console', []))}")
        print(f"Handler types: {handlers_by_type}")
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
