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

from .session_factory import (
    create_session_factory,
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
    # URL Caching
    'URLCache',
    'RichURLCache',
    'DEFAULT_CACHE_EXPIRY_DAYS',
    # Session factory
    'create_session_factory',
    # Sentry integration
    'init_sentry',
    'capture_scraper_error',
    'capture_message',
    'set_retailer_context',
    'add_breadcrumb',
    'start_transaction',
    'sentry_flush',
]
