"""HTTP utility functions for web scraping.

This module provides HTTP request helpers including retry logic,
session management, and header generation.
"""

import logging
import random
import time
from typing import Dict, Optional

import requests

from src.shared.constants import HTTP
from src.shared.proxy_client import redact_credentials

__all__ = [
    'DEFAULT_USER_AGENTS',
    'get_headers',
    'get_with_retry',
]


# Default user agents for rotation
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]


def get_headers(user_agent: str = None, base_url: str = None) -> Dict[str, str]:
    """Get headers dict with optional user agent rotation.

    Args:
        user_agent: User agent string (random if not provided)
        base_url: Base URL for Referer header (defaults to Google)

    Returns:
        Dictionary of HTTP headers
    """
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


def get_with_retry(
    session: requests.Session,
    url: str,
    max_retries: int = None,
    timeout: int = None,
    rate_limit_base_wait: int = None,
    min_delay: float = None,
    max_delay: float = None,
    headers_func=None,
) -> Optional[requests.Response]:
    """Fetch URL with exponential backoff retry and proper error handling.

    This function makes HTTP GET requests with retry logic for transient failures.
    Instead of mutating session.headers, it passes headers per-request to avoid
    side effects when the session is shared across threads.

    Args:
        session: requests.Session to use
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
        rate_limit_base_wait: Base wait time for 429 errors
        min_delay: Minimum delay between requests
        max_delay: Maximum delay between requests
        headers_func: Optional function to get headers (for config integration)

    Returns:
        Response object on success, None on failure
    """
    from src.shared.delays import random_delay

    max_retries = max_retries if max_retries is not None else HTTP.MAX_RETRIES
    timeout = timeout if timeout is not None else HTTP.TIMEOUT
    rate_limit_base_wait = rate_limit_base_wait if rate_limit_base_wait is not None else HTTP.RATE_LIMIT_BASE_WAIT

    # Get headers for this request
    if headers_func:
        headers = headers_func()
    else:
        headers = get_headers()

    response = None  # Initialize response to prevent AttributeError

    for attempt in range(max_retries):
        try:
            random_delay(min_delay, max_delay)
            # Pass headers per-request instead of mutating session.headers (#206)
            response = session.get(url, headers=headers, timeout=timeout)

            # Redact credentials from URL for safe logging (prevents leaking proxy credentials)
            safe_url = redact_credentials(url)

            # Check if response is valid before accessing attributes
            if response is None:
                logging.warning(f"Received None response for {safe_url}")  # lgtm[py/clear-text-logging-sensitive-data] safe_url is sanitized
                continue

            if response.status_code == 200:
                logging.debug(f"Successfully fetched {safe_url}")  # lgtm[py/clear-text-logging-sensitive-data] safe_url is sanitized
                return response

            if response.status_code == 429:  # Rate limited
                wait_time = (2 ** attempt) * rate_limit_base_wait
                logging.warning(f"Rate limited (429) for {safe_url}. Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")  # lgtm[py/clear-text-logging-sensitive-data] safe_url is sanitized
                time.sleep(wait_time)

            elif response.status_code == 403:  # Blocked
                # Use exponential backoff starting at 30s (#144)
                wait_time = (2 ** attempt) * rate_limit_base_wait
                # lgtm[py/clear-text-logging-sensitive-data] safe_url is sanitized by redact_credentials()
                logging.warning(
                    f"Blocked (403) for {safe_url}. "
                    f"Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)
                # Continue to retry instead of immediate return (#144)

            elif response.status_code >= 500:  # Server error
                wait_time = HTTP.SERVER_ERROR_WAIT
                logging.warning(f"Server error ({response.status_code}) for {safe_url}. Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")  # lgtm[py/clear-text-logging-sensitive-data] safe_url is sanitized
                time.sleep(wait_time)

            elif response.status_code == 408:  # Request timeout - might succeed on retry
                wait_time = HTTP.SERVER_ERROR_WAIT
                logging.warning(f"Request timeout (408) for {safe_url}. Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")  # lgtm[py/clear-text-logging-sensitive-data] safe_url is sanitized
                time.sleep(wait_time)

            elif 400 <= response.status_code < 500:  # Client errors (4xx) - fail fast except 403/429/408
                # 404, 401, 410, etc. won't succeed on retry
                logging.error(f"Client error ({response.status_code}) for {safe_url}. Failing immediately.")  # lgtm[py/clear-text-logging-sensitive-data] safe_url is sanitized
                return None

            else:
                # 3xx redirects should be handled by requests library, but log unexpected codes
                logging.warning(f"Unexpected HTTP {response.status_code} for {safe_url}")  # lgtm[py/clear-text-logging-sensitive-data] safe_url is sanitized
                return None

        except requests.exceptions.RequestException as e:
            response = None  # Ensure response is None after exception
            wait_time = HTTP.SERVER_ERROR_WAIT
            # Redact credentials from error messages and URLs to prevent leaking sensitive info
            safe_url = redact_credentials(url)
            safe_error = redact_credentials(str(e))
            logging.warning(f"Request error for {safe_url}: {safe_error}. Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")  # lgtm[py/clear-text-logging-sensitive-data] safe_url and safe_error are sanitized
            time.sleep(wait_time)

    # Log final failure with context (#144)
    safe_url = redact_credentials(url)
    final_status = response.status_code if response else 'no response'
    logging.error(f"Failed to fetch {safe_url} after {max_retries} attempts (last status: {final_status})")  # lgtm[py/clear-text-logging-sensitive-data] safe_url is sanitized
    return None
