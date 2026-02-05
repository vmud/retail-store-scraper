"""Tests for centralized constants module - Issue #171.

TDD approach: These tests are written BEFORE the constants module exists.
They will fail initially and drive the implementation.
"""

import pytest
from dataclasses import FrozenInstanceError


class TestConstantsModuleExists:
    """Verify the constants module can be imported."""

    def test_constants_module_importable(self):
        """The constants module should be importable."""
        from src.shared import constants
        assert constants is not None

    def test_all_singleton_instances_exist(self):
        """All singleton constant instances should be available."""
        from src.shared.constants import (
            HTTP, CACHE, PAUSE, WORKERS, PROGRESS,
            EXPORT, LOGGING, RUN_HISTORY, STREAMING,
            STATUS, TEST_MODE, VALIDATION
        )
        # All should be non-None
        assert HTTP is not None
        assert CACHE is not None
        assert PAUSE is not None
        assert WORKERS is not None
        assert PROGRESS is not None
        assert EXPORT is not None
        assert LOGGING is not None
        assert RUN_HISTORY is not None
        assert STREAMING is not None
        assert STATUS is not None
        assert TEST_MODE is not None
        assert VALIDATION is not None


class TestHttpDefaults:
    """Test HTTP request defaults."""

    def test_min_delay_value(self):
        """MIN_DELAY should be 2.0 seconds."""
        from src.shared.constants import HTTP
        assert HTTP.MIN_DELAY == 2.0

    def test_max_delay_value(self):
        """MAX_DELAY should be 5.0 seconds."""
        from src.shared.constants import HTTP
        assert HTTP.MAX_DELAY == 5.0

    def test_max_retries_value(self):
        """MAX_RETRIES should be 3."""
        from src.shared.constants import HTTP
        assert HTTP.MAX_RETRIES == 3

    def test_timeout_value(self):
        """TIMEOUT should be 30 seconds."""
        from src.shared.constants import HTTP
        assert HTTP.TIMEOUT == 30

    def test_rate_limit_base_wait_value(self):
        """RATE_LIMIT_BASE_WAIT should be 30 seconds."""
        from src.shared.constants import HTTP
        assert HTTP.RATE_LIMIT_BASE_WAIT == 30

    def test_server_error_wait_value(self):
        """SERVER_ERROR_WAIT should be 10 seconds."""
        from src.shared.constants import HTTP
        assert HTTP.SERVER_ERROR_WAIT == 10

    def test_http_is_frozen(self):
        """HTTP dataclass should be immutable."""
        from src.shared.constants import HTTP
        with pytest.raises(FrozenInstanceError):
            HTTP.MIN_DELAY = 999


class TestCacheDefaults:
    """Test cache expiry settings."""

    def test_url_cache_expiry_days(self):
        """URL cache expiry should be 7 days."""
        from src.shared.constants import CACHE
        assert CACHE.URL_CACHE_EXPIRY_DAYS == 7

    def test_response_cache_expiry_days(self):
        """Response cache expiry should be 30 days."""
        from src.shared.constants import CACHE
        assert CACHE.RESPONSE_CACHE_EXPIRY_DAYS == 30

    def test_cache_is_frozen(self):
        """CACHE dataclass should be immutable."""
        from src.shared.constants import CACHE
        with pytest.raises(FrozenInstanceError):
            CACHE.URL_CACHE_EXPIRY_DAYS = 999


class TestPauseDefaults:
    """Test rate limiting pause thresholds."""

    def test_short_threshold(self):
        """Short pause threshold should be 50 requests."""
        from src.shared.constants import PAUSE
        assert PAUSE.SHORT_THRESHOLD == 50

    def test_short_min_seconds(self):
        """Short pause min should be 30 seconds."""
        from src.shared.constants import PAUSE
        assert PAUSE.SHORT_MIN_SECONDS == 30.0

    def test_short_max_seconds(self):
        """Short pause max should be 60 seconds."""
        from src.shared.constants import PAUSE
        assert PAUSE.SHORT_MAX_SECONDS == 60.0

    def test_long_threshold(self):
        """Long pause threshold should be 200 requests."""
        from src.shared.constants import PAUSE
        assert PAUSE.LONG_THRESHOLD == 200

    def test_long_min_seconds(self):
        """Long pause min should be 120 seconds."""
        from src.shared.constants import PAUSE
        assert PAUSE.LONG_MIN_SECONDS == 120.0

    def test_long_max_seconds(self):
        """Long pause max should be 180 seconds."""
        from src.shared.constants import PAUSE
        assert PAUSE.LONG_MAX_SECONDS == 180.0

    def test_disabled_threshold(self):
        """Disabled threshold should be 999999."""
        from src.shared.constants import PAUSE
        assert PAUSE.DISABLED_THRESHOLD == 999999

    def test_pause_is_frozen(self):
        """PAUSE dataclass should be immutable."""
        from src.shared.constants import PAUSE
        with pytest.raises(FrozenInstanceError):
            PAUSE.SHORT_THRESHOLD = 999


class TestWorkerDefaults:
    """Test parallel worker configuration."""

    def test_executor_max_workers(self):
        """Executor max workers should be 6."""
        from src.shared.constants import WORKERS
        assert WORKERS.EXECUTOR_MAX_WORKERS == 6

    def test_proxied_workers(self):
        """Proxied workers should be 5."""
        from src.shared.constants import WORKERS
        assert WORKERS.PROXIED_WORKERS == 5

    def test_direct_workers(self):
        """Direct workers should be 1."""
        from src.shared.constants import WORKERS
        assert WORKERS.DIRECT_WORKERS == 1

    def test_discovery_workers_proxied(self):
        """Discovery workers (proxied) should be 10."""
        from src.shared.constants import WORKERS
        assert WORKERS.DISCOVERY_WORKERS_PROXIED == 10

    def test_discovery_workers_direct(self):
        """Discovery workers (direct) should be 1."""
        from src.shared.constants import WORKERS
        assert WORKERS.DISCOVERY_WORKERS_DIRECT == 1

    def test_workers_is_frozen(self):
        """WORKERS dataclass should be immutable."""
        from src.shared.constants import WORKERS
        with pytest.raises(FrozenInstanceError):
            WORKERS.PROXIED_WORKERS = 999


class TestProgressDefaults:
    """Test progress logging intervals."""

    def test_short_interval(self):
        """Short progress interval should be 10."""
        from src.shared.constants import PROGRESS
        assert PROGRESS.SHORT_INTERVAL == 10

    def test_medium_interval(self):
        """Medium progress interval should be 50."""
        from src.shared.constants import PROGRESS
        assert PROGRESS.MEDIUM_INTERVAL == 50

    def test_long_interval(self):
        """Long progress interval should be 100."""
        from src.shared.constants import PROGRESS
        assert PROGRESS.LONG_INTERVAL == 100

    def test_progress_is_frozen(self):
        """PROGRESS dataclass should be immutable."""
        from src.shared.constants import PROGRESS
        with pytest.raises(FrozenInstanceError):
            PROGRESS.SHORT_INTERVAL = 999


class TestExportDefaults:
    """Test export configuration."""

    def test_field_sample_size(self):
        """Field sample size should be 100."""
        from src.shared.constants import EXPORT
        assert EXPORT.FIELD_SAMPLE_SIZE == 100

    def test_excel_max_column_width(self):
        """Excel max column width should be 50."""
        from src.shared.constants import EXPORT
        assert EXPORT.EXCEL_MAX_COLUMN_WIDTH == 50

    def test_excel_sheet_name_max(self):
        """Excel sheet name max should be 31."""
        from src.shared.constants import EXPORT
        assert EXPORT.EXCEL_SHEET_NAME_MAX == 31

    def test_export_is_frozen(self):
        """EXPORT dataclass should be immutable."""
        from src.shared.constants import EXPORT
        with pytest.raises(FrozenInstanceError):
            EXPORT.FIELD_SAMPLE_SIZE = 999


class TestLoggingDefaults:
    """Test logging configuration."""

    def test_max_bytes(self):
        """Max bytes should be 10MB."""
        from src.shared.constants import LOGGING
        assert LOGGING.MAX_BYTES == 10 * 1024 * 1024

    def test_backup_count(self):
        """Backup count should be 5."""
        from src.shared.constants import LOGGING
        assert LOGGING.BACKUP_COUNT == 5

    def test_logging_is_frozen(self):
        """LOGGING dataclass should be immutable."""
        from src.shared.constants import LOGGING
        with pytest.raises(FrozenInstanceError):
            LOGGING.MAX_BYTES = 999


class TestRunHistoryDefaults:
    """Test run history settings."""

    def test_history_limit(self):
        """History limit should be 10."""
        from src.shared.constants import RUN_HISTORY
        assert RUN_HISTORY.HISTORY_LIMIT == 10

    def test_cleanup_keep(self):
        """Cleanup keep should be 20."""
        from src.shared.constants import RUN_HISTORY
        assert RUN_HISTORY.CLEANUP_KEEP == 20

    def test_run_history_is_frozen(self):
        """RUN_HISTORY dataclass should be immutable."""
        from src.shared.constants import RUN_HISTORY
        with pytest.raises(FrozenInstanceError):
            RUN_HISTORY.HISTORY_LIMIT = 999


class TestStreamingDefaults:
    """Test streaming/memory thresholds."""

    def test_large_file_threshold_bytes(self):
        """Large file threshold should be 50MB."""
        from src.shared.constants import STREAMING
        assert STREAMING.LARGE_FILE_THRESHOLD_BYTES == 50 * 1024 * 1024

    def test_streaming_is_frozen(self):
        """STREAMING dataclass should be immutable."""
        from src.shared.constants import STREAMING
        with pytest.raises(FrozenInstanceError):
            STREAMING.LARGE_FILE_THRESHOLD_BYTES = 999


class TestStatusDefaults:
    """Test status monitoring."""

    def test_active_threshold_seconds(self):
        """Active threshold should be 300 seconds (5 min)."""
        from src.shared.constants import STATUS
        assert STATUS.ACTIVE_THRESHOLD_SECONDS == 300

    def test_notification_timeout(self):
        """Notification timeout should be 10 seconds."""
        from src.shared.constants import STATUS
        assert STATUS.NOTIFICATION_TIMEOUT == 10

    def test_status_is_frozen(self):
        """STATUS dataclass should be immutable."""
        from src.shared.constants import STATUS
        with pytest.raises(FrozenInstanceError):
            STATUS.ACTIVE_THRESHOLD_SECONDS = 999


class TestTestModeDefaults:
    """Test test mode configuration."""

    def test_store_limit(self):
        """Test mode store limit should be 10."""
        from src.shared.constants import TEST_MODE
        assert TEST_MODE.STORE_LIMIT == 10

    def test_grid_spacing_miles(self):
        """Test mode grid spacing should be 200 miles."""
        from src.shared.constants import TEST_MODE
        assert TEST_MODE.GRID_SPACING_MILES == 200

    def test_test_mode_is_frozen(self):
        """TEST_MODE dataclass should be immutable."""
        from src.shared.constants import TEST_MODE
        with pytest.raises(FrozenInstanceError):
            TEST_MODE.STORE_LIMIT = 999


class TestValidationDefaults:
    """Test data validation bounds."""

    def test_lat_min(self):
        """Latitude min should be -90."""
        from src.shared.constants import VALIDATION
        assert VALIDATION.LAT_MIN == -90.0

    def test_lat_max(self):
        """Latitude max should be 90."""
        from src.shared.constants import VALIDATION
        assert VALIDATION.LAT_MAX == 90.0

    def test_lon_min(self):
        """Longitude min should be -180."""
        from src.shared.constants import VALIDATION
        assert VALIDATION.LON_MIN == -180.0

    def test_lon_max(self):
        """Longitude max should be 180."""
        from src.shared.constants import VALIDATION
        assert VALIDATION.LON_MAX == 180.0

    def test_zip_length_short(self):
        """Short ZIP length should be 5."""
        from src.shared.constants import VALIDATION
        assert VALIDATION.ZIP_LENGTH_SHORT == 5

    def test_zip_length_long(self):
        """Long ZIP length should be 10."""
        from src.shared.constants import VALIDATION
        assert VALIDATION.ZIP_LENGTH_LONG == 10

    def test_error_log_limit(self):
        """Error log limit should be 10."""
        from src.shared.constants import VALIDATION
        assert VALIDATION.ERROR_LOG_LIMIT == 10

    def test_validation_is_frozen(self):
        """VALIDATION dataclass should be immutable."""
        from src.shared.constants import VALIDATION
        with pytest.raises(FrozenInstanceError):
            VALIDATION.LAT_MIN = 999


class TestBackwardCompatibility:
    """Test backward compatibility with existing DEFAULT_* constants."""

    def test_default_min_delay_still_works(self):
        """DEFAULT_MIN_DELAY in utils.py should still work."""
        from src.shared.utils import DEFAULT_MIN_DELAY
        from src.shared.constants import HTTP
        assert DEFAULT_MIN_DELAY == HTTP.MIN_DELAY

    def test_default_max_delay_still_works(self):
        """DEFAULT_MAX_DELAY in utils.py should still work."""
        from src.shared.utils import DEFAULT_MAX_DELAY
        from src.shared.constants import HTTP
        assert DEFAULT_MAX_DELAY == HTTP.MAX_DELAY

    def test_default_max_retries_still_works(self):
        """DEFAULT_MAX_RETRIES in utils.py should still work."""
        from src.shared.utils import DEFAULT_MAX_RETRIES
        from src.shared.constants import HTTP
        assert DEFAULT_MAX_RETRIES == HTTP.MAX_RETRIES

    def test_default_timeout_still_works(self):
        """DEFAULT_TIMEOUT in utils.py should still work."""
        from src.shared.utils import DEFAULT_TIMEOUT
        from src.shared.constants import HTTP
        assert DEFAULT_TIMEOUT == HTTP.TIMEOUT

    def test_default_rate_limit_base_wait_still_works(self):
        """DEFAULT_RATE_LIMIT_BASE_WAIT in utils.py should still work."""
        from src.shared.utils import DEFAULT_RATE_LIMIT_BASE_WAIT
        from src.shared.constants import HTTP
        assert DEFAULT_RATE_LIMIT_BASE_WAIT == HTTP.RATE_LIMIT_BASE_WAIT


class TestDataclassTypes:
    """Verify dataclass field types are correct."""

    def test_http_field_types(self):
        """HTTP fields should have correct types."""
        from src.shared.constants import HTTP
        assert isinstance(HTTP.MIN_DELAY, float)
        assert isinstance(HTTP.MAX_DELAY, float)
        assert isinstance(HTTP.MAX_RETRIES, int)
        assert isinstance(HTTP.TIMEOUT, int)
        assert isinstance(HTTP.RATE_LIMIT_BASE_WAIT, int)
        assert isinstance(HTTP.SERVER_ERROR_WAIT, int)

    def test_pause_field_types(self):
        """PAUSE fields should have correct types."""
        from src.shared.constants import PAUSE
        assert isinstance(PAUSE.SHORT_THRESHOLD, int)
        assert isinstance(PAUSE.SHORT_MIN_SECONDS, float)
        assert isinstance(PAUSE.SHORT_MAX_SECONDS, float)
        assert isinstance(PAUSE.LONG_THRESHOLD, int)
        assert isinstance(PAUSE.LONG_MIN_SECONDS, float)
        assert isinstance(PAUSE.LONG_MAX_SECONDS, float)
        assert isinstance(PAUSE.DISABLED_THRESHOLD, int)

    def test_validation_field_types(self):
        """VALIDATION fields should have correct types."""
        from src.shared.constants import VALIDATION
        assert isinstance(VALIDATION.LAT_MIN, float)
        assert isinstance(VALIDATION.LAT_MAX, float)
        assert isinstance(VALIDATION.LON_MIN, float)
        assert isinstance(VALIDATION.LON_MAX, float)
        assert isinstance(VALIDATION.ZIP_LENGTH_SHORT, int)
        assert isinstance(VALIDATION.ZIP_LENGTH_LONG, int)
        assert isinstance(VALIDATION.ERROR_LOG_LIMIT, int)


class TestAllExport:
    """Verify __all__ export list is correct."""

    def test_constants_has_all_export(self):
        """constants.py should have __all__ defined."""
        from src.shared import constants
        assert hasattr(constants, '__all__')

    def test_all_singletons_in_all_export(self):
        """All singleton instances should be in __all__."""
        from src.shared import constants
        expected = [
            'HTTP', 'CACHE', 'PAUSE', 'WORKERS', 'PROGRESS',
            'EXPORT', 'LOGGING', 'RUN_HISTORY', 'STREAMING',
            'STATUS', 'TEST_MODE', 'VALIDATION',
            # Also include dataclass types
            'HttpDefaults', 'CacheDefaults', 'PauseDefaults',
            'WorkerDefaults', 'ProgressDefaults', 'ExportDefaults',
            'LoggingDefaults', 'RunHistoryDefaults', 'StreamingDefaults',
            'StatusDefaults', 'TestModeDefaults', 'ValidationDefaults',
        ]
        for item in expected:
            assert item in constants.__all__, f"{item} should be in __all__"
