"""Tests for traceback logging in run_all_retailers."""
import asyncio
import logging
import pytest
from unittest.mock import patch, AsyncMock

from run import run_all_retailers


class TestRunAllRetailersTracebacks:
    """Tests for full traceback logging (#145)."""

    @pytest.mark.asyncio
    async def test_exception_traceback_is_logged(self, caplog):
        """When a retailer raises an exception, the full traceback should be logged."""

        # Create a mock that raises an exception with a traceback
        async def failing_retailer(*args, **kwargs):
            def inner_function():
                raise ValueError("Test error from inner function")
            inner_function()

        with patch('run.run_retailer_async', side_effect=failing_retailer), \
             caplog.at_level(logging.ERROR):
            results = await run_all_retailers(['test_retailer'])

        # Check that the error was captured
        assert 'test_retailer' in results
        assert results['test_retailer']['status'] == 'error'

        # Check that traceback info was logged (should contain 'inner_function')
        # When using exc_info=, the traceback is in caplog.text (formatted output)
        # not in record.message
        log_text = caplog.text
        assert 'Traceback' in log_text, f"Expected 'Traceback' in logs, got: {log_text}"
        assert 'inner_function' in log_text, f"Expected 'inner_function' in logs, got: {log_text}"

    @pytest.mark.asyncio
    async def test_retailer_name_included_in_error_log(self, caplog):
        """Retailer name should be included in error context."""

        async def failing_retailer(*args, **kwargs):
            raise RuntimeError("Connection failed")

        with patch('run.run_retailer_async', side_effect=failing_retailer), \
             caplog.at_level(logging.ERROR):
            results = await run_all_retailers(['verizon'])

        # Should include retailer name in error logging
        log_text = '\n'.join(record.message for record in caplog.records)
        assert 'verizon' in log_text.lower(), f"Expected 'verizon' in error log, got: {log_text}"
