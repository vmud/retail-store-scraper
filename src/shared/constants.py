"""Centralized constants for the retail store scraper - Issue #171.

This module provides frozen dataclass-based configuration groups for all
magic numbers used throughout the codebase. Using dataclasses provides:
- Type safety and IDE autocompletion
- Immutability (frozen=True prevents accidental modification)
- Clear documentation via docstrings
- Grouped related constants logically

Usage:
    from src.shared.constants import HTTP, CACHE, WORKERS

    timeout = HTTP.TIMEOUT
    cache_days = CACHE.URL_CACHE_EXPIRY_DAYS
    workers = WORKERS.PROXIED_WORKERS if using_proxy else WORKERS.DIRECT_WORKERS
"""

from dataclasses import dataclass

__all__ = [
    'CACHE',
    'CacheDefaults',
    'EXPORT',
    'ExportDefaults',
    'HTTP',
    'HttpDefaults',
    'LOGGING',
    'LoggingDefaults',
    'PAUSE',
    'PauseDefaults',
    'PROGRESS',
    'ProgressDefaults',
    'RUN_HISTORY',
    'RunHistoryDefaults',
    'STATUS',
    'StatusDefaults',
    'STREAMING',
    'StreamingDefaults',
    'TEST_MODE',
    'TestModeDefaults',
    'VALIDATION',
    'ValidationDefaults',
    'WORKERS',
    'WorkerDefaults',
]


@dataclass(frozen=True)
class HttpDefaults:
    """HTTP request configuration defaults.

    These values control retry behavior, timeouts, and delays between requests.
    They can be overridden per-retailer in config/retailers.yaml.
    """

    MIN_DELAY: float = 2.0
    """Minimum delay between requests in seconds."""

    MAX_DELAY: float = 5.0
    """Maximum delay between requests in seconds."""

    MAX_RETRIES: int = 3
    """Maximum number of retry attempts for failed requests."""

    TIMEOUT: int = 30
    """Request timeout in seconds."""

    RATE_LIMIT_BASE_WAIT: int = 30
    """Base wait time in seconds when receiving 429 (rate limit) responses."""

    SERVER_ERROR_WAIT: int = 10
    """Wait time in seconds after server errors (5xx) or timeouts before retry."""


@dataclass(frozen=True)
class CacheDefaults:
    """Cache expiry settings.

    Controls how long cached data remains valid before requiring refresh.
    """

    URL_CACHE_EXPIRY_DAYS: int = 7
    """Number of days to cache discovered store URLs."""

    RESPONSE_CACHE_EXPIRY_DAYS: int = 30
    """Number of days to cache HTTP responses (e.g., Walmart sitemap)."""


@dataclass(frozen=True)
class PauseDefaults:
    """Rate limiting pause thresholds.

    Controls when and how long the scraper pauses to avoid overwhelming
    target servers. Pauses occur at request count thresholds.
    """

    SHORT_THRESHOLD: int = 50
    """Request count threshold for short pause (every N requests)."""

    SHORT_MIN_SECONDS: float = 30.0
    """Minimum duration for short pause in seconds."""

    SHORT_MAX_SECONDS: float = 60.0
    """Maximum duration for short pause in seconds."""

    LONG_THRESHOLD: int = 200
    """Request count threshold for long pause (every N requests)."""

    LONG_MIN_SECONDS: float = 120.0
    """Minimum duration for long pause in seconds."""

    LONG_MAX_SECONDS: float = 180.0
    """Maximum duration for long pause in seconds."""

    DISABLED_THRESHOLD: int = 999999
    """Magic value to effectively disable pause thresholds."""


@dataclass(frozen=True)
class WorkerDefaults:
    """Parallel worker configuration.

    Controls concurrent request handling. Proxied requests can use more
    workers because IP rotation reduces rate limiting risk.
    """

    EXECUTOR_MAX_WORKERS: int = 6
    """Maximum workers for ThreadPoolExecutor in run.py."""

    PROXIED_WORKERS: int = 5
    """Default number of workers when using proxy."""

    DIRECT_WORKERS: int = 1
    """Default number of workers without proxy (conservative)."""

    DISCOVERY_WORKERS_PROXIED: int = 10
    """Workers for URL discovery phase when using proxy (Verizon)."""

    DISCOVERY_WORKERS_DIRECT: int = 1
    """Workers for URL discovery phase without proxy."""


@dataclass(frozen=True)
class ProgressDefaults:
    """Progress logging intervals.

    Controls how frequently progress messages are logged during scraping.
    """

    SHORT_INTERVAL: int = 10
    """Log progress every N stores (for quick feedback)."""

    MEDIUM_INTERVAL: int = 50
    """Log progress every N stores (balanced)."""

    LONG_INTERVAL: int = 100
    """Log progress every N stores (less verbose)."""


@dataclass(frozen=True)
class ExportDefaults:
    """Export configuration.

    Controls data export behavior for JSON, CSV, and Excel formats.
    """

    FIELD_SAMPLE_SIZE: int = 100
    """Number of records to sample for field discovery in exports."""

    EXCEL_MAX_COLUMN_WIDTH: int = 50
    """Maximum column width in Excel exports."""

    EXCEL_SHEET_NAME_MAX: int = 31
    """Maximum characters for Excel sheet names (Excel limitation)."""


@dataclass(frozen=True)
class LoggingDefaults:
    """Logging configuration.

    Controls log file rotation settings.
    """

    MAX_BYTES: int = 10 * 1024 * 1024
    """Maximum log file size before rotation (10MB)."""

    BACKUP_COUNT: int = 5
    """Number of backup log files to keep."""


@dataclass(frozen=True)
class RunHistoryDefaults:
    """Run history settings.

    Controls run metadata tracking and cleanup.
    """

    HISTORY_LIMIT: int = 10
    """Default number of run history entries to retrieve."""

    CLEANUP_KEEP: int = 20
    """Number of old runs to keep during cleanup."""


@dataclass(frozen=True)
class StreamingDefaults:
    """Streaming and memory thresholds.

    Controls when to use streaming vs in-memory processing.
    """

    LARGE_FILE_THRESHOLD_BYTES: int = 50 * 1024 * 1024
    """File size threshold (50MB) above which streaming is used."""


@dataclass(frozen=True)
class StatusDefaults:
    """Status monitoring configuration.

    Controls status reporting and notification behavior.
    """

    ACTIVE_THRESHOLD_SECONDS: int = 300
    """Time in seconds (5 minutes) before a process is considered inactive."""

    NOTIFICATION_TIMEOUT: int = 10
    """Timeout in seconds for notification requests (e.g., Slack)."""


@dataclass(frozen=True)
class TestModeDefaults:
    """Test mode configuration.

    Controls behavior when running in test mode (--test flag).
    """

    STORE_LIMIT: int = 10
    """Maximum stores to scrape per retailer in test mode."""

    GRID_SPACING_MILES: int = 200
    """Grid spacing in miles for geo-based test sampling."""


@dataclass(frozen=True)
class ValidationDefaults:
    """Data validation bounds.

    Controls store data validation rules.
    """

    LAT_MIN: float = -90.0
    """Minimum valid latitude."""

    LAT_MAX: float = 90.0
    """Maximum valid latitude."""

    LON_MIN: float = -180.0
    """Minimum valid longitude."""

    LON_MAX: float = 180.0
    """Maximum valid longitude."""

    ZIP_LENGTH_SHORT: int = 5
    """Length of short US ZIP code (e.g., 12345)."""

    ZIP_LENGTH_LONG: int = 10
    """Length of long US ZIP+4 code (e.g., 12345-6789)."""

    ERROR_LOG_LIMIT: int = 10
    """Maximum validation errors to log before truncating."""


# Singleton instances for easy import
HTTP = HttpDefaults()
CACHE = CacheDefaults()
PAUSE = PauseDefaults()
WORKERS = WorkerDefaults()
PROGRESS = ProgressDefaults()
EXPORT = ExportDefaults()
LOGGING = LoggingDefaults()
RUN_HISTORY = RunHistoryDefaults()
STREAMING = StreamingDefaults()
STATUS = StatusDefaults()
TEST_MODE = TestModeDefaults()
VALIDATION = ValidationDefaults()
