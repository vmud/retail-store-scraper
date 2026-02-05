"""Shared utilities for all scrapers"""

from .utils import (
    setup_logging,
    random_delay,
    get_with_retry,
    get_headers,
    save_checkpoint,
    load_checkpoint,
    save_to_csv,
    save_to_json,
    DEFAULT_MIN_DELAY,
    DEFAULT_MAX_DELAY,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    DEFAULT_RATE_LIMIT_BASE_WAIT,
    DEFAULT_USER_AGENTS,
    # Oxylabs proxy integration
    get_proxy_client,
    get_with_proxy,
    init_proxy_from_yaml,
    create_proxied_session,
    close_proxy_client,
    close_all_proxy_clients,
    ProxiedSession,
    # Per-retailer proxy configuration
    get_retailer_proxy_config,
    load_retailer_config,
    # Concurrency configuration
    configure_concurrency_from_yaml,
)

from .proxy_client import (
    ProxyClient,
    ProxyConfig,
    ProxyMode,
    ProxyResponse,
    create_proxy_client,
)

from .scraper_manager import (
    ScraperManager,
    get_scraper_manager,
)

from .run_tracker import (
    RunTracker,
    get_run_history,
    get_latest_run,
    get_active_run,
    cleanup_old_runs,
)

from .status import (
    get_retailer_status,
    get_all_retailers_status,
    get_progress_status,
    load_retailers_config,
)

from .cache import (
    URLCache,
    RichURLCache,
    DEFAULT_CACHE_EXPIRY_DAYS,
)

from .cache_interface import (
    CacheInterface,
    URLListCache,
    RichURLCache as RichURLCacheInterface,
    ResponseCache,
)

from .session_factory import (
    create_session_factory,
)

from .concurrency import (
    GlobalConcurrencyManager,
    ConcurrencyConfig,
)

from .store_serializer import (
    Store,
    StoreSerializer,
    normalize_store_dict,
)

from .structured_logging import (
    LogEvent,
    EventType,
    Phase,
    StructuredLogger,
    MetricsAggregator,
    create_logger,
)
from .sentry_integration import (
    init_sentry,
    capture_scraper_error,
    capture_message,
    set_retailer_context,
    add_breadcrumb,
    start_transaction,
    flush as sentry_flush,
)

__all__ = [
    # Core utilities
    'setup_logging',
    'random_delay',
    'get_with_retry',
    'get_headers',
    'save_checkpoint',
    'load_checkpoint',
    'save_to_csv',
    'save_to_json',
    'DEFAULT_MIN_DELAY',
    'DEFAULT_MAX_DELAY',
    'DEFAULT_MAX_RETRIES',
    'DEFAULT_TIMEOUT',
    'DEFAULT_RATE_LIMIT_BASE_WAIT',
    'DEFAULT_USER_AGENTS',
    # Oxylabs proxy integration
    'ProxyClient',
    'ProxyConfig',
    'ProxyMode',
    'ProxyResponse',
    'create_proxy_client',
    'get_proxy_client',
    'get_with_proxy',
    'init_proxy_from_yaml',
    'create_proxied_session',
    'close_proxy_client',
    'close_all_proxy_clients',
    'ProxiedSession',
    # Per-retailer proxy configuration
    'get_retailer_proxy_config',
    'load_retailer_config',
    # Concurrency configuration
    'configure_concurrency_from_yaml',
    # Scraper management
    'ScraperManager',
    'get_scraper_manager',
    # Run tracking
    'RunTracker',
    'get_run_history',
    'get_latest_run',
    'get_active_run',
    'cleanup_old_runs',
    # Status tracking
    'get_retailer_status',
    'get_all_retailers_status',
    'get_progress_status',
    'load_retailers_config',
    # URL Caching (legacy)
    'URLCache',
    'RichURLCache',
    'DEFAULT_CACHE_EXPIRY_DAYS',
    # Unified Cache Interface
    'CacheInterface',
    'URLListCache',
    'RichURLCacheInterface',
    'ResponseCache',
    # Session factory
    'create_session_factory',
    # Concurrency management
    'GlobalConcurrencyManager',
    'ConcurrencyConfig',
    # Store schema and serialization
    'Store',
    'StoreSerializer',
    'normalize_store_dict',
    # Structured logging and metrics
    'LogEvent',
    'EventType',
    'Phase',
    'StructuredLogger',
    'MetricsAggregator',
    'create_logger',
    # Sentry integration
    'init_sentry',
    'capture_scraper_error',
    'capture_message',
    'set_retailer_context',
    'add_breadcrumb',
    'start_transaction',
    'sentry_flush',
]
