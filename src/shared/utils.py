"""Shared utility functions for all retailer scrapers"""

import json
import csv
import time
import random
import logging
import tempfile
import shutil
import os
import threading
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

import requests

# Import proxy client for Oxylabs integration
from src.shared.proxy_client import ProxyClient, ProxyConfig, ProxyMode, ProxyResponse, redact_credentials

# Import centralized constants (Issue #171)
from src.shared.constants import HTTP, LOGGING, VALIDATION


# Default configuration values - backward compatible aliases to centralized constants
# These can be overridden per-retailer in config/retailers.yaml
DEFAULT_MIN_DELAY = HTTP.MIN_DELAY
DEFAULT_MAX_DELAY = HTTP.MAX_DELAY
DEFAULT_MAX_RETRIES = HTTP.MAX_RETRIES
DEFAULT_TIMEOUT = HTTP.TIMEOUT
DEFAULT_RATE_LIMIT_BASE_WAIT = HTTP.RATE_LIMIT_BASE_WAIT

# Default user agents for rotation
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

# Global proxy client instances (lazy initialized per retailer)
_proxy_clients: Dict[str, ProxyClient] = {}
_proxy_clients_lock = threading.Lock()

# Thread lock for setup_logging to prevent duplicate handlers (#163)
_logging_lock = threading.Lock()


def setup_logging(log_file: str = "logs/scraper.log", max_bytes: int = LOGGING.MAX_BYTES, backup_count: int = LOGGING.BACKUP_COUNT) -> None:
    """Setup logging configuration with rotation (#118).

    This function is idempotent and thread-safe - calling it multiple times
    or from multiple threads will not add duplicate handlers (#143, #163).

    Args:
        log_file: Path to log file
        max_bytes: Maximum file size before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
    """
    from logging.handlers import RotatingFileHandler

    # Thread-safe handler setup (#163)
    with _logging_lock:
        root_logger = logging.getLogger()
        log_path = Path(log_file)

        # Idempotency check for file handler: skip if handler exists with matching configuration
        has_file_handler = False
        for handler in root_logger.handlers[:]:  # Copy list to allow modification during iteration
            if isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(log_path.absolute()):
                # Check if configuration matches
                if handler.maxBytes == max_bytes and handler.backupCount == backup_count:
                    has_file_handler = True
                    break
                # Configuration mismatch - remove old handler to reconfigure
                root_logger.removeHandler(handler)
                handler.close()

        # Idempotency check for console handler (#143): skip if one already exists
        # Use FileHandler (not RotatingFileHandler) to exclude ALL file-based handlers
        # since FileHandler is the base class for all file handlers including RotatingFileHandler
        has_console_handler = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
            for h in root_logger.handlers
        )

        # Return early if both handlers already exist
        if has_file_handler and has_console_handler:
            return

        # Ensure log directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        root_logger.setLevel(logging.INFO)

        # Add file handler if needed
        if not has_file_handler:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        # Add console handler if needed (#143)
        if not has_console_handler:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)


def get_headers(user_agent: str = None, base_url: str = None) -> Dict[str, str]:
    """Get headers dict with optional user agent rotation"""
    if user_agent is None:
        user_agent = random.choice(DEFAULT_USER_AGENTS)

    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": base_url or "https://www.google.com",
    }


def random_delay(min_sec: float = None, max_sec: float = None) -> None:
    """Add randomized delay between requests"""
    min_sec = min_sec if min_sec is not None else DEFAULT_MIN_DELAY
    max_sec = max_sec if max_sec is not None else DEFAULT_MAX_DELAY
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    logging.debug(f"Delayed {delay:.2f} seconds")


def select_delays(config: dict, proxy_mode: str) -> tuple:
    """Select appropriate delays based on proxy mode.
    
    Args:
        config: Retailer configuration dict
        proxy_mode: Proxy mode string ('direct', 'residential', 'web_scraper_api')
    
    Returns:
        Tuple of (min_delay, max_delay)
    
    Examples:
        >>> select_delays({'delays': {'direct': {'min_delay': 2.0, 'max_delay': 5.0}, 
        ...                            'proxied': {'min_delay': 0.2, 'max_delay': 0.5}}}, 
        ...               'residential')
        (0.2, 0.5)
    """
    # Check if config has dual delay profiles
    if 'delays' in config:
        delays_config = config['delays']
        
        # Use proxied delays for any proxy mode except 'direct'
        if proxy_mode and proxy_mode != 'direct':
            if 'proxied' in delays_config:
                return (
                    delays_config['proxied'].get('min_delay', DEFAULT_MIN_DELAY),
                    delays_config['proxied'].get('max_delay', DEFAULT_MAX_DELAY)
                )
        
        # Use direct mode delays
        if 'direct' in delays_config:
            return (
                delays_config['direct'].get('min_delay', DEFAULT_MIN_DELAY),
                delays_config['direct'].get('max_delay', DEFAULT_MAX_DELAY)
            )
    
    # Fallback to legacy min_delay/max_delay fields
    return (
        config.get('min_delay', DEFAULT_MIN_DELAY),
        config.get('max_delay', DEFAULT_MAX_DELAY)
    )


def get_with_retry(
    session: requests.Session,
    url: str,
    max_retries: int = None,
    timeout: int = None,
    rate_limit_base_wait: int = None,
    min_delay: float = None,
    max_delay: float = None,
    headers_func = None,
) -> Optional[requests.Response]:
    """Fetch URL with exponential backoff retry and proper error handling

    Args:
        session: requests.Session to use
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
        rate_limit_base_wait: Base wait time for 429 errors
        min_delay: Minimum delay between requests
        max_delay: Maximum delay between requests
        headers_func: Optional function to get headers (for config integration)
    """
    max_retries = max_retries if max_retries is not None else DEFAULT_MAX_RETRIES
    timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
    rate_limit_base_wait = rate_limit_base_wait if rate_limit_base_wait is not None else DEFAULT_RATE_LIMIT_BASE_WAIT

    # Rotate user agent
    if headers_func:
        headers = headers_func()
    else:
        headers = get_headers()
    session.headers.update(headers)

    response = None  # Initialize response to prevent AttributeError
    
    for attempt in range(max_retries):
        try:
            random_delay(min_delay, max_delay)
            response = session.get(url, timeout=timeout)

            # Check if response is valid before accessing attributes
            if response is None:
                logging.warning(f"Received None response for {url}")
                continue

            if response.status_code == 200:
                logging.debug(f"Successfully fetched {url}")
                return response

            if response.status_code == 429:  # Rate limited
                wait_time = (2 ** attempt) * rate_limit_base_wait
                logging.warning(f"Rate limited (429) for {url}. Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)

            elif response.status_code == 403:  # Blocked
                # Use exponential backoff starting at 30s (#144)
                wait_time = (2 ** attempt) * rate_limit_base_wait
                logging.warning(
                    f"Blocked (403) for {url}. "
                    f"Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)
                # Continue to retry instead of immediate return (#144)

            elif response.status_code >= 500:  # Server error
                wait_time = HTTP.SERVER_ERROR_WAIT
                logging.warning(f"Server error ({response.status_code}) for {url}. Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)

            elif response.status_code == 408:  # Request timeout - might succeed on retry
                wait_time = HTTP.SERVER_ERROR_WAIT
                logging.warning(f"Request timeout (408) for {url}. Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)

            elif 400 <= response.status_code < 500:  # Client errors (4xx) - fail fast except 403/429/408
                # 404, 401, 410, etc. won't succeed on retry
                logging.error(f"Client error ({response.status_code}) for {url}. Failing immediately.")
                return None

            else:
                # 3xx redirects should be handled by requests library, but log unexpected codes
                logging.warning(f"Unexpected HTTP {response.status_code} for {url}")
                return None

        except requests.exceptions.RequestException as e:
            response = None  # Ensure response is None after exception
            wait_time = HTTP.SERVER_ERROR_WAIT
            # Redact credentials from error messages to prevent leaking sensitive info
            safe_error = redact_credentials(str(e))
            logging.warning(f"Request error for {url}: {safe_error}. Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(wait_time)

    # Log final failure with context (#144)
    final_status = response.status_code if response else 'no response'
    logging.error(f"Failed to fetch {url} after {max_retries} attempts (last status: {final_status})")
    return None


def save_checkpoint(data: Any, filepath: str) -> None:
    """Save progress to allow resuming using atomic write (temp file + rename)"""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temporary file first, then rename atomically
    # This prevents corruption if interrupted during write
    try:
        # Create temp file in same directory to ensure atomic rename works
        temp_fd, temp_path = tempfile.mkstemp(
            suffix='.tmp',
            dir=path.parent,
            prefix=path.name + '.'
        )

        try:
            # Write JSON to temp file using os.fdopen to properly manage the fd
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            # Atomic rename: os.replace is atomic on POSIX and Windows
            # shutil.move is not guaranteed atomic on all filesystems
            os.replace(temp_path, str(path))
            logging.info(f"Checkpoint saved: {filepath}")

        except Exception as e:
            # Close the fd if fdopen failed and it's still open
            try:
                os.close(temp_fd)
            except OSError:
                pass
            # Clean up temp file on error
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass
            raise e

    except (IOError, OSError) as e:
        logging.error(f"Failed to save checkpoint {filepath}: {e}")
        raise


def load_checkpoint(filepath: str) -> Optional[Any]:
    """Load previous progress"""
    path = Path(filepath)
    if not path.exists():
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logging.info(f"Checkpoint loaded: {filepath}")
        return data
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.warning(f"Failed to load checkpoint {filepath}: {e}")
        return None


def save_to_csv(stores: List[Dict[str, Any]], filepath: str, fieldnames: List[str] = None) -> None:
    """Save stores to CSV

    Args:
        stores: List of store dictionaries
        filepath: Path to save CSV file
        fieldnames: Optional list of field names (uses default if not provided)
    """
    if not stores:
        logging.warning("No stores to save")
        return

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Default fieldnames for basic store data
    if fieldnames is None:
        fieldnames = ['name', 'street_address', 'city', 'state', 'zip',
                      'country', 'latitude', 'longitude', 'phone', 'url', 'scraped_at']

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(stores)

    logging.info(f"Saved {len(stores)} stores to CSV: {filepath}")


def save_to_json(stores: List[Dict[str, Any]], filepath: str) -> None:
    """Save stores to JSON"""
    if not stores:
        logging.warning("No stores to save")
        return

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(stores, f, indent=2, ensure_ascii=False)

    logging.info(f"Saved {len(stores)} stores to JSON: {filepath}")


# =============================================================================
# STORE DATA VALIDATION (#103)
# =============================================================================

# Required fields that must be present and non-empty
REQUIRED_STORE_FIELDS = {'store_id', 'name', 'street_address', 'city', 'state'}

# Recommended fields that should be present for data quality
RECOMMENDED_STORE_FIELDS = {'latitude', 'longitude', 'phone', 'url'}


class ValidationResult:
    """Result of store data validation"""

    def __init__(self, is_valid: bool, errors: List[str], warnings: List[str]):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings

    def __repr__(self) -> str:
        return f"ValidationResult(is_valid={self.is_valid}, errors={len(self.errors)}, warnings={len(self.warnings)})"


def validate_store_data(store: Dict[str, Any], strict: bool = False) -> ValidationResult:
    """Validate store data completeness and correctness.

    Args:
        store: Store data dictionary to validate
        strict: If True, treat missing recommended fields as errors

    Returns:
        ValidationResult with is_valid status, errors list, and warnings list
    """
    errors = []
    warnings = []

    # Check required fields
    for field in REQUIRED_STORE_FIELDS:
        value = store.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"Missing required field: {field}")

    # Check recommended fields
    for field in RECOMMENDED_STORE_FIELDS:
        if store.get(field) is None:
            if strict:
                errors.append(f"Missing recommended field: {field}")
            else:
                warnings.append(f"Missing recommended field: {field}")

    # Validate coordinates if present
    lat, lng = store.get('latitude'), store.get('longitude')
    if lat is not None and lng is not None:
        try:
            lat_float = float(lat)
            lng_float = float(lng)
            if not (VALIDATION.LAT_MIN <= lat_float <= VALIDATION.LAT_MAX):
                errors.append(f"Invalid latitude: {lat} (must be between {VALIDATION.LAT_MIN} and {VALIDATION.LAT_MAX})")
            if not (VALIDATION.LON_MIN <= lng_float <= VALIDATION.LON_MAX):
                errors.append(f"Invalid longitude: {lng} (must be between {VALIDATION.LON_MIN} and {VALIDATION.LON_MAX})")
        except (ValueError, TypeError):
            errors.append(f"Invalid coordinate format: lat={lat}, lng={lng}")

    # Validate postal code format (US 5-digit or 9-digit)
    postal_code = store.get('postal_code') or store.get('zip_code')
    if postal_code:
        postal_str = str(postal_code).strip()
        if postal_str and not (len(postal_str) == VALIDATION.ZIP_LENGTH_SHORT or len(postal_str) == VALIDATION.ZIP_LENGTH_LONG):
            # ZIP_LENGTH_LONG (10) for "12345-6789" format
            warnings.append(f"Unusual postal code format: {postal_code}")

    return ValidationResult(len(errors) == 0, errors, warnings)


def validate_stores_batch(
    stores: List[Dict[str, Any]],
    strict: bool = False,
    log_issues: bool = True
) -> Dict[str, Any]:
    """Validate a batch of stores and return summary.

    Args:
        stores: List of store data dictionaries
        strict: If True, treat missing recommended fields as errors
        log_issues: If True, log validation issues

    Returns:
        Dictionary with validation summary
    """
    total = len(stores)
    valid_count = 0
    invalid_stores = []
    all_errors = []
    all_warnings = []

    for i, store in enumerate(stores):
        result = validate_store_data(store, strict=strict)
        if result.is_valid:
            valid_count += 1
        else:
            store_id = store.get('store_id', f'index_{i}')
            invalid_stores.append(store_id)
            all_errors.extend([f"Store {store_id}: {e}" for e in result.errors])

        all_warnings.extend(result.warnings)

    if log_issues:
        if all_errors:
            for error in all_errors[:VALIDATION.ERROR_LOG_LIMIT]:
                logging.warning(error)
            if len(all_errors) > VALIDATION.ERROR_LOG_LIMIT:
                logging.warning(f"... and {len(all_errors) - VALIDATION.ERROR_LOG_LIMIT} more validation errors")

    return {
        'total': total,
        'valid': valid_count,
        'invalid': total - valid_count,
        'invalid_store_ids': invalid_stores,
        'error_count': len(all_errors),
        'warning_count': len(all_warnings),
    }


# =============================================================================
# PER-RETAILER PROXY CONFIGURATION
# =============================================================================

def _build_proxy_config_dict(mode: str, **kwargs) -> Dict[str, Any]:
    """Build proxy config dict from mode string and optional overrides"""
    config = {'mode': mode}
    config.update(kwargs)
    return config


def _merge_proxy_config(
    retailer_proxy: Dict[str, Any],
    global_proxy: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge retailer-specific proxy config with global settings.
    Retailer settings take precedence.
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
    """Build config dict from global YAML proxy section"""
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
    """Apply CLI proxy settings without mutating base config."""
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
    """
    Get proxy configuration for specific retailer with priority resolution.

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


def load_retailer_config(
    retailer: str,
    cli_proxy_override: Optional[str] = None,
    cli_proxy_settings: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Load full retailer configuration including proxy settings.

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
    """
    Get or create a proxy client instance.

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
    """
    Initialize proxy client from retailers.yaml configuration.
    
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
    """
    Fetch URL using proxy client (Oxylabs integration).

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
) -> Union[requests.Session, "ProxiedSession"]:
    """
    Create a session-like object that can be used as a drop-in replacement
    for requests.Session in existing scrapers.

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
    """Close all proxy client sessions and clear cache"""
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
    """
    A wrapper that provides requests.Session-like interface but uses
    ProxyClient under the hood. This allows existing scrapers to work
    with minimal changes.

    Each ProxiedSession owns its own ProxyClient instance to avoid
    shared state issues when running multiple scrapers concurrently
    with different proxy configurations.

    Usage:
        # Instead of: session = requests.Session()
        session = ProxiedSession(proxy_config)
        response = session.get(url)  # Uses proxy if configured
    """

    def __init__(self, proxy_config: Optional[Dict[str, Any]] = None):
        """
        Initialize proxied session with its own dedicated ProxyClient.

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
        """Lazy-create direct session if needed"""
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
        **kwargs
    ) -> Optional[Union[requests.Response, ProxyResponse]]:
        """
        Make GET request using configured proxy mode.

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
        """Close the session and its owned resources"""
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

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
