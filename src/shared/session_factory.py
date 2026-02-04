"""Session factory for retail store scrapers.

This module provides a unified session creation function that replaces the
duplicate `_create_session_factory()` implementations across individual scrapers.

requests.Session is NOT thread-safe, so each worker thread in parallel
scrapers needs its own session instance. This factory pattern ensures
consistent session configuration across all scrapers.
"""

from typing import Callable

import requests

from src.shared import utils


__all__ = [
    'create_session_factory',
]


def create_session_factory(retailer_config: dict) -> Callable[[], requests.Session]:
    """Create a factory function that produces per-worker sessions.

    requests.Session is NOT thread-safe, so each worker thread needs its own
    session instance. This factory creates new sessions with the same proxy
    configuration as specified in the retailer config.

    Args:
        retailer_config: Retailer configuration dict from retailers.yaml with proxy settings

    Returns:
        Callable that creates new configured session instances

    Usage:
        # In parallel scraper
        session_factory = create_session_factory(config)

        with ThreadPoolExecutor(max_workers=5) as executor:
            for url in urls:
                executor.submit(extract_store, url, session_factory)

        # In worker function
        def extract_store(url, session_factory):
            session = session_factory()
            try:
                response = session.get(url)
                ...
            finally:
                session.close()
    """
    def factory() -> requests.Session:
        return utils.create_proxied_session(retailer_config)

    return factory
