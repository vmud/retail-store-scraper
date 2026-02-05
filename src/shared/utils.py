"""Shared utility functions for all retailer scrapers.

This module serves as a backwards-compatible facade, re-exporting functions
from focused modules. It also contains proxy-related utilities that integrate
multiple concerns.

For new code, prefer importing from the specific modules:
- src.shared.http - HTTP request helpers
- src.shared.checkpoint - Checkpoint save/load
- src.shared.delays - Delay and rate limiting
- src.shared.validation - Store data validation
- src.shared.logging_config - Logging setup
- src.shared.io - File I/O (deprecated, use ExportService)
"""

import logging
import os
import threading
from types import TracebackType
from typing import Any, Dict, List, Optional, Type, Union

import requests
import yaml

# Import from focused modules for re-export
from src.shared.checkpoint import load_checkpoint, save_checkpoint
from src.shared.delays import (
    DEFAULT_MAX_DELAY,
    DEFAULT_MIN_DELAY,
    random_delay,
    select_delays,
)
from src.shared.http import DEFAULT_USER_AGENTS, get_headers, get_with_retry
from src.shared.io import save_to_csv, save_to_json
from src.shared.logging_config import setup_logging
from src.shared.validation import (
    RECOMMENDED_STORE_FIELDS,
    REQUIRED_STORE_FIELDS,
    ValidationResult,
    validate_store_data,
    validate_stores_batch,
)

# Import proxy client for Oxylabs integration
from src.shared.proxy_client import (
    ProxyClient,
    ProxyConfig,
    ProxyMode,
    ProxyResponse,
    redact_credentials,
)

# Import centralized constants (Issue #171)
from src.shared.constants import HTTP

# Import canonical field definitions and normalization (Issue #170)
from src.shared.store_schema import (
    CANONICAL_FIELDS,
    FIELD_ALIASES,
    RECOMMENDED_STORE_FIELDS,
    REQUIRED_STORE_FIELDS,
    normalize_store_data,
    normalize_stores_batch,
)

__all__ = [
    'CANONICAL_FIELDS',
    'DEFAULT_MAX_DELAY',
    'DEFAULT_MAX_RETRIES',
    'DEFAULT_MIN_DELAY',
    'DEFAULT_RATE_LIMIT_BASE_WAIT',
    'DEFAULT_TIMEOUT',
    'DEFAULT_USER_AGENTS',
    'FIELD_ALIASES',
    'ProxiedSession',
    'RECOMMENDED_STORE_FIELDS',
    'REQUIRED_STORE_FIELDS',
    'ValidationResult',
    'close_all_proxy_clients',
    'close_proxy_client',
    'configure_concurrency_from_yaml',
    'create_proxied_session',
    'get_headers',
    'get_proxy_client',
    'get_retailer_proxy_config',
    'get_with_proxy',
    'get_with_retry',
    'init_proxy_from_yaml',
    'load_checkpoint',
    'load_retailer_config',
    'normalize_store_data',
    'normalize_stores_batch',
    'random_delay',
    'save_checkpoint',
    'save_to_csv',
    'save_to_json',
    'select_delays',
    'setup_logging',
    'validate_store_data',
    'validate_stores_batch',
]


# Default configuration values - backward compatible aliases to centralized constants
# These can be overridden per-retailer in config/retailers.yaml
DEFAULT_MAX_RETRIES = HTTP.MAX_RETRIES
DEFAULT_TIMEOUT = HTTP.TIMEOUT
DEFAULT_RATE_LIMIT_BASE_WAIT = HTTP.RATE_LIMIT_BASE_WAIT

# Global proxy client instances (lazy initialized per retailer)
_proxy_clients: Dict[str, ProxyClient] = {}
_proxy_clients_lock = threading.Lock()


# =============================================================================
# PER-RETAILER PROXY CONFIGURATION
# =============================================================================

def _build_proxy_config_dict(mode: str, **kwargs) -> Dict[str, Any]:
    """Build proxy config dict from mode string and optional overrides.

    Args:
        mode: Proxy mode ('direct', 'residential', 'web_scraper_api')
        **kwargs: Additional configuration parameters

    Returns:
        Proxy configuration dictionary
    """
    config = {'mode': mode}
    config.update(kwargs)
    return config


def _merge_proxy_config(
    retailer_proxy: Dict[str, Any],
    global_proxy: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge retailer-specific proxy config with global settings.

    Retailer settings take precedence over global settings.

    Args:
        retailer_proxy: Retailer-specific proxy configuration
        global_proxy: Global proxy configuration

    Returns:
        Merged configuration dictionary
    """
    mode = retailer_proxy.get('mode', global_proxy.get('mode', 'direct'))

    config = {'mode': mode}

    if mode == 'residential' and 'residential' in global_proxy:
        config.update(global_proxy['residential'])
    elif mode == 'web_scraper_api' and 'web_scraper_api' in global_proxy:
        config.update(global_proxy['web_scraper_api'])

    for key in ['timeout', 'max_retries', 'retry_delay']:
        if key in global_proxy:
            config[key] = global_proxy[key]

    config.update(retailer_proxy)

    return config


def _build_proxy_config_from_yaml(global_proxy: Dict[str, Any]) -> Dict[str, Any]:
    """Build config dict from global YAML proxy section.

    Args:
        global_proxy: Global proxy section from YAML

    Returns:
        Proxy configuration dictionary
    """
    mode = global_proxy.get('mode', 'direct')
    config = {'mode': mode}

    if mode == 'residential' and 'residential' in global_proxy:
        config.update(global_proxy['residential'])
    elif mode == 'web_scraper_api' and 'web_scraper_api' in global_proxy:
        config.update(global_proxy['web_scraper_api'])

    for key in ['timeout', 'max_retries', 'retry_delay']:
        if key in global_proxy:
            config[key] = global_proxy[key]

    return config


def _apply_cli_settings(
    base_config: Dict[str, Any],
    cli_settings: Dict[str, Any]
) -> Dict[str, Any]:
    """Apply CLI proxy settings without mutating base config.

    Args:
        base_config: Base configuration dictionary
        cli_settings: CLI-provided settings to apply

    Returns:
        Updated configuration dictionary
    """
    if not cli_settings:
        return base_config
    updated_config = dict(base_config)
    updated_config.update(cli_settings)
    return updated_config


def get_retailer_proxy_config(
    retailer: str,
    yaml_path: str = "config/retailers.yaml",
    cli_override: Optional[str] = None,
    cli_settings: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Get proxy configuration for specific retailer with priority resolution.

    Priority (highest to lowest):
    1. CLI override (--proxy flag and related options)
    2. Retailer-specific config in YAML
    3. Global proxy section in YAML
    4. Environment variables (PROXY_MODE)
    5. Default: direct mode

    Args:
        retailer: Retailer name
        yaml_path: Path to retailers.yaml file
        cli_override: CLI proxy mode override (from --proxy flag)
        cli_settings: Additional CLI proxy settings (country_code, render_js, etc.)

    Returns:
        Dict compatible with ProxyConfig.from_dict()
    """
    VALID_MODES = {'direct', 'residential', 'web_scraper_api'}
    cli_settings = {
        key: value
        for key, value in (cli_settings or {}).items()
        if value is not None
    }

    if cli_override:
        if cli_override not in VALID_MODES:
            logging.warning(f"[{retailer}] Invalid CLI proxy mode '{cli_override}', falling back to direct")
            return _build_proxy_config_dict(mode='direct')
        logging.info(f"[{retailer}] Using CLI override proxy mode: {cli_override}")
        # Include all CLI settings in the config (#52)
        config = _build_proxy_config_dict(mode=cli_override)
        return _apply_cli_settings(config, cli_settings)

    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logging.warning(f"[{retailer}] Config file {yaml_path} not found")
        config = {}
    except Exception as e:
        logging.warning(f"[{retailer}] Error loading config: {e}")
        config = {}

    # Handle empty YAML files (safe_load returns None)
    config = config or {}

    retailer_config = config.get('retailers', {}).get(retailer, {})
    if 'proxy' in retailer_config:
        proxy_settings = retailer_config['proxy']
        merged_config = _merge_proxy_config(proxy_settings, config.get('proxy', {}))
        mode = merged_config.get('mode', 'direct')
        if mode not in VALID_MODES:
            logging.warning(f"[{retailer}] Invalid retailer proxy mode '{mode}', falling back to direct")
            merged_config['mode'] = 'direct'
        else:
            logging.info(f"[{retailer}] Using retailer-specific proxy mode: {mode}")
        return _apply_cli_settings(merged_config, cli_settings)

    if 'proxy' in config:
        proxy_config = _build_proxy_config_from_yaml(config['proxy'])
        mode = proxy_config.get('mode', 'direct')
        if mode not in VALID_MODES:
            logging.warning(f"[{retailer}] Invalid global proxy mode '{mode}', falling back to direct")
            proxy_config['mode'] = 'direct'
        else:
            logging.info(f"[{retailer}] Using global YAML proxy mode: {mode}")
        return _apply_cli_settings(proxy_config, cli_settings)

    env_mode = os.getenv('PROXY_MODE')
    if env_mode:
        if env_mode not in VALID_MODES:
            logging.warning(f"[{retailer}] Invalid environment proxy mode '{env_mode}', falling back to direct")
            return _build_proxy_config_dict(mode='direct')
        logging.info(f"[{retailer}] Using environment variable proxy mode: {env_mode}")
        env_config = _build_proxy_config_dict(mode=env_mode)
        return _apply_cli_settings(env_config, cli_settings)

    logging.info(f"[{retailer}] Using default proxy mode: direct")
    return _apply_cli_settings({'mode': 'direct'}, cli_settings)


def configure_concurrency_from_yaml(config_path: str = 'config/retailers.yaml') -> None:
    """Configure GlobalConcurrencyManager from retailers.yaml (Issue #153).

    Loads concurrency configuration from YAML and applies it to the singleton
    GlobalConcurrencyManager instance. Should be called once at startup.

    Args:
        config_path: Path to retailers.yaml config file

    Example YAML structure:
        concurrency:
          global_max_workers: 10
          per_retailer_max:
            verizon: 7
            target: 5
          proxy_rate_limit: 10.0
    """
    from src.shared.concurrency import GlobalConcurrencyManager

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logging.warning(f"Config file {config_path} not found, using default concurrency limits")
        return
    except yaml.YAMLError as e:
        logging.error(f"Error parsing {config_path}: {e}, using default concurrency limits")
        return

    if not config or 'concurrency' not in config:
        logging.debug("No concurrency section in config, using defaults")
        return

    concurrency_config = config['concurrency']
    manager = GlobalConcurrencyManager()

    # Extract configuration values
    # Note: dict.get() returns None (not default) if key exists with null value
    # so we need to explicitly handle None values
    global_max_workers = concurrency_config.get('global_max_workers')
    per_retailer_max = concurrency_config.get('per_retailer_max')
    if per_retailer_max is None:
        per_retailer_max = {}
    proxy_rate_limit = concurrency_config.get('proxy_rate_limit')

    # Configure the manager
    manager.configure(
        global_max_workers=global_max_workers,
        per_retailer_max=per_retailer_max if per_retailer_max else None,
        proxy_requests_per_second=proxy_rate_limit
    )

    logging.info(
        f"[ConcurrencyManager] Configured from YAML: "
        f"global_max={global_max_workers}, "
        f"retailers={len(per_retailer_max)}, "
        f"proxy_rate={proxy_rate_limit}"
    )


def load_retailer_config(
    retailer: str,
    cli_proxy_override: Optional[str] = None,
    cli_proxy_settings: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Load full retailer configuration including proxy settings.

    Args:
        retailer: Retailer name
        cli_proxy_override: Optional CLI proxy mode override (--proxy flag)
        cli_proxy_settings: Optional CLI proxy settings (country_code, render_js, etc.)

    Returns:
        Dict with retailer config including 'proxy' key
    """
    try:
        with open('config/retailers.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logging.error(f"[{retailer}] Config file config/retailers.yaml not found")
        return {'proxy': {'mode': 'direct'}, 'name': retailer}
    except Exception as e:
        logging.error(f"[{retailer}] Error loading config: {e}")
        return {'proxy': {'mode': 'direct'}, 'name': retailer}

    # Handle empty YAML files (safe_load returns None)
    config = config or {}

    retailer_config = config.get('retailers', {}).get(retailer, {})

    # Add retailer name to config for logging purposes (#117)
    retailer_config['name'] = retailer

    # Get proxy config with CLI overrides (#52)
    proxy_config = get_retailer_proxy_config(
        retailer,
        cli_override=cli_proxy_override,
        cli_settings=cli_proxy_settings
    )
    retailer_config['proxy'] = proxy_config

    return retailer_config


# =============================================================================
# OXYLABS PROXY INTEGRATION
# =============================================================================

def get_proxy_client(config: Optional[Dict[str, Any]] = None, retailer: Optional[str] = None) -> ProxyClient:
    """Get or create a proxy client instance.

    If retailer is specified, returns/creates retailer-specific client.
    Otherwise returns/creates global client.

    Args:
        config: Optional proxy configuration dictionary. If None, loads from
                environment variables.
        retailer: Optional retailer name for per-retailer client caching

    Returns:
        Configured ProxyClient instance
    """
    global _proxy_clients

    cache_key = retailer if retailer else '__global__'

    with _proxy_clients_lock:
        if cache_key in _proxy_clients and config is None:
            return _proxy_clients[cache_key]

        # Close existing client before overwriting to prevent resource leak
        if cache_key in _proxy_clients:
            try:
                _proxy_clients[cache_key].close()
            except Exception:
                pass

        if config:
            proxy_config = ProxyConfig.from_dict(config)
        else:
            proxy_config = ProxyConfig.from_env()

        client = ProxyClient(proxy_config)
        _proxy_clients[cache_key] = client

        return client


def init_proxy_from_yaml(yaml_path: str = "config/retailers.yaml") -> ProxyClient:
    """Initialize proxy client from retailers.yaml configuration.

    Deprecated: Use get_retailer_proxy_config() + create_proxied_session() for new code.
    This function loads global proxy config and caches it under '__global__' key.

    Args:
        yaml_path: Path to retailers.yaml file

    Returns:
        Configured ProxyClient instance
    """
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        proxy_config = config.get('proxy', {})
        mode = proxy_config.get('mode', 'direct')

        config_dict = {
            'mode': mode,
            'timeout': proxy_config.get('timeout', 60),
            'max_retries': proxy_config.get('max_retries', 3),
            'retry_delay': proxy_config.get('retry_delay', 2.0),
        }

        if mode == 'residential':
            res_config = proxy_config.get('residential', {})
            config_dict.update({
                'residential_endpoint': res_config.get('endpoint', 'pr.oxylabs.io:7777'),
                'country_code': res_config.get('country_code', 'us'),
                'session_type': res_config.get('session_type', 'rotating'),
            })
        elif mode == 'web_scraper_api':
            api_config = proxy_config.get('web_scraper_api', {})
            config_dict.update({
                'scraper_api_endpoint': api_config.get('endpoint', 'https://realtime.oxylabs.io/v1/queries'),
                'render_js': api_config.get('render_js', False),
                'parse': api_config.get('parse', False),
            })

        client = get_proxy_client(config_dict)
        logging.info(f"Initialized proxy client from {yaml_path} in {mode} mode")
        return client

    except FileNotFoundError:
        logging.warning(f"Config file {yaml_path} not found, using environment config")
        return get_proxy_client()
    except Exception as e:
        logging.warning(f"Error loading proxy config from {yaml_path}: {e}, using environment config")
        return get_proxy_client()


def get_with_proxy(
    url: str,
    proxy_config: Optional[Dict[str, Any]] = None,
    render_js: Optional[bool] = None,
    timeout: Optional[int] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Optional[Union[requests.Response, ProxyResponse]]:
    """Fetch URL using proxy client (Oxylabs integration).

    This is the recommended function for new code. It automatically handles:
    - Proxy rotation (residential mode)
    - JavaScript rendering (web_scraper_api mode)
    - Retries and rate limiting
    - CAPTCHA bypass (via Oxylabs)

    Args:
        url: URL to fetch
        proxy_config: Optional per-request proxy config override
        render_js: Override JS rendering (for web_scraper_api mode)
        timeout: Request timeout in seconds
        headers: Optional custom headers

    Returns:
        ProxyResponse object or None on failure
    """
    client = get_proxy_client(proxy_config)
    return client.get(url, headers=headers, render_js=render_js, timeout=timeout)


def create_proxied_session(
    retailer_config: Optional[Dict[str, Any]] = None
) -> Union[requests.Session, 'ProxiedSession']:
    """Create a session-like object that can be used as a drop-in replacement for requests.Session.

    For direct mode, returns a standard requests.Session.
    For proxy modes, returns a ProxiedSession with compatible interface.

    Args:
        retailer_config: Optional retailer-specific config with proxy overrides

    Returns:
        Session-compatible object
    """
    proxy_config_dict = retailer_config.get('proxy', {}) if retailer_config else {}
    mode = proxy_config_dict.get('mode', 'direct')
    retailer_name = retailer_config.get('name', 'unknown') if retailer_config else 'unknown'

    if mode == 'direct':
        session = requests.Session()
        session.headers.update(get_headers())
        logging.info(f"[{retailer_name}] Created Session for mode: {mode}")
        return session

    try:
        # Check credentials before creating client to properly detect missing credentials
        # ProxyClient.__init__ silently falls back to DIRECT mode if credentials are missing,
        # so we need to validate beforehand to provide the correct fallback behavior
        test_config = ProxyConfig.from_dict(proxy_config_dict)
        if not test_config.validate():
            logging.error(f"[{retailer_name}] Missing credentials for {mode} mode, falling back to direct")
            session = requests.Session()
            session.headers.update(get_headers())
            return session

        # Return ProxiedSession instead of ProxyClient to provide headers attribute
        proxied_session = ProxiedSession(proxy_config_dict)

        logging.info(f"[{retailer_name}] Created ProxiedSession for mode: {mode}")
        return proxied_session

    except Exception as e:
        # Redact credentials from error messages
        safe_error = redact_credentials(str(e))
        logging.error(f"[{retailer_name}] Error creating proxy client: {safe_error}, falling back to direct")
        session = requests.Session()
        session.headers.update(get_headers())
        return session


def close_proxy_client() -> None:
    """Close the global proxy client and release resources.

    Deprecated: Use close_all_proxy_clients() for new code.
    """
    global _proxy_clients
    with _proxy_clients_lock:
        if '__global__' in _proxy_clients:
            _proxy_clients['__global__'].close()
            del _proxy_clients['__global__']
            logging.info("Global proxy client closed")


def close_all_proxy_clients() -> None:
    """Close all proxy client sessions and clear cache."""
    global _proxy_clients

    with _proxy_clients_lock:
        for name, client in _proxy_clients.items():
            try:
                client.close()
                logging.debug(f"Closed proxy client: {name}")
            except Exception as e:
                logging.warning(f"Error closing proxy client {name}: {e}")

        _proxy_clients.clear()
        logging.info("All proxy clients closed")


class ProxiedSession:
    """A wrapper that provides requests.Session-like interface using ProxyClient.

    This allows existing scrapers to work with minimal changes.

    Each ProxiedSession owns its own ProxyClient instance to avoid
    shared state issues when running multiple scrapers concurrently
    with different proxy configurations.

    Usage:
        # Instead of: session = requests.Session()
        session = ProxiedSession(proxy_config)
        response = session.get(url)  # Uses proxy if configured
    """

    def __init__(self, proxy_config: Optional[Dict[str, Any]] = None):
        """Initialize proxied session with its own dedicated ProxyClient.

        Args:
            proxy_config: Optional proxy configuration dict
        """
        # Create a dedicated ProxyClient instance for this session
        # instead of sharing from the global cache to avoid concurrent
        # scraper configurations interfering with each other (#53)
        if proxy_config:
            config = ProxyConfig.from_dict(proxy_config)
        else:
            config = ProxyConfig.from_env()
        self._client = ProxyClient(config)
        self._owns_client = True  # Track that we own this client for cleanup
        self._direct_session: Optional[requests.Session] = None
        self.headers: Dict[str, str] = get_headers()

    @property
    def _session(self) -> requests.Session:
        """Lazy-create direct session if needed."""
        if self._direct_session is None:
            self._direct_session = requests.Session()
            self._direct_session.headers.update(self.headers)
        return self._direct_session

    def get(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs: Any
    ) -> Optional[Union[requests.Response, ProxyResponse]]:
        """Make GET request using configured proxy mode.

        Args:
            url: URL to fetch
            params: Query parameters
            headers: Custom headers
            timeout: Request timeout
            **kwargs: Additional arguments (passed to underlying client)

        Returns:
            Response object or None on failure
        """
        merged_headers = {**self.headers, **(headers or {})}

        if self._client.config.mode == ProxyMode.DIRECT:
            # Use standard session for direct mode
            try:
                self._session.headers.update(merged_headers)
                response = self._session.get(url, params=params, timeout=timeout or 30, **kwargs)
                return response
            except requests.exceptions.RequestException as e:
                # Redact credentials from error messages
                safe_error = redact_credentials(str(e))
                logging.warning(f"Request error: {safe_error}")
                return None
        else:
            # Use proxy client
            return self._client.get(url, params=params, headers=merged_headers, timeout=timeout)

    def close(self) -> None:
        """Close the session and its owned resources."""
        if self._direct_session:
            self._direct_session.close()
            self._direct_session = None
        # Close the dedicated client if we own it (#53)
        if self._owns_client and self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def __enter__(self) -> "ProxiedSession":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> None:
        """Exit context manager and close resources.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception instance if an exception occurred
            exc_tb: Traceback object if an exception occurred
        """
        self.close()
