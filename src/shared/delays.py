"""Delay and pause utilities for rate limiting.

This module provides functions for adding delays between requests
to avoid overwhelming target servers and triggering anti-bot measures.
"""

import logging
import random
import time
from typing import Tuple

from src.shared.constants import HTTP

__all__ = [
    'DEFAULT_MAX_DELAY',
    'DEFAULT_MIN_DELAY',
    'random_delay',
    'select_delays',
]


# Default configuration values - backward compatible aliases to centralized constants
DEFAULT_MIN_DELAY = HTTP.MIN_DELAY
DEFAULT_MAX_DELAY = HTTP.MAX_DELAY


def random_delay(min_sec: float = None, max_sec: float = None) -> None:
    """Add randomized delay between requests.

    Args:
        min_sec: Minimum delay in seconds (uses default if None)
        max_sec: Maximum delay in seconds (uses default if None)
    """
    min_sec = min_sec if min_sec is not None else DEFAULT_MIN_DELAY
    max_sec = max_sec if max_sec is not None else DEFAULT_MAX_DELAY
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    logging.debug(f"Delayed {delay:.2f} seconds")


def select_delays(config: dict, proxy_mode: str) -> Tuple[float, float]:
    """Select appropriate delays based on proxy mode.

    Retailers can define separate delay profiles for direct and proxied requests.
    When using residential proxies, shorter delays can be used safely due to IP rotation.

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
