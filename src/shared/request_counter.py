"""Shared request counter for tracking requests across scrapers."""

import logging
import random
import threading
import time

from src.shared.constants import PAUSE


class RequestCounter:
    """Thread-safe request counter for tracking requests across scrapers.

    Uses a threading lock to ensure atomic increment operations when
    multiple scrapers run concurrently.
    """

    def __init__(self):
        """Initialize request counter with zero count and thread lock."""
        self._count = 0
        self._lock = threading.Lock()

    @property
    def count(self) -> int:
        """Current request count with thread-safe access.

        Returns:
            Current request count.
        """
        with self._lock:
            return self._count

    def increment(self) -> int:
        """Increment counter and return current count (thread-safe).

        Returns:
            Updated request count after increment.
        """
        with self._lock:
            self._count += 1
            return self._count

    def reset(self) -> None:
        """Reset counter to zero with thread-safe access."""
        with self._lock:
            self._count = 0

    def get_count(self) -> int:
        """Get current count without incrementing (thread-safe).

        Returns:
            Current request count.
        """
        with self._lock:
            return self._count


def check_pause_logic(
    counter: RequestCounter,
    retailer: str = None,
    config: dict = None,
    pause_50_requests: int = PAUSE.SHORT_THRESHOLD,
    pause_50_min: float = PAUSE.SHORT_MIN_SECONDS,
    pause_50_max: float = PAUSE.SHORT_MAX_SECONDS,
    pause_200_requests: int = PAUSE.LONG_THRESHOLD,
    pause_200_min: float = PAUSE.LONG_MIN_SECONDS,
    pause_200_max: float = PAUSE.LONG_MAX_SECONDS,
) -> None:
    """Check if we need to pause based on request count (#71).

    If config is provided, it can contain keys that override the default
    values for the pause-related arguments (e.g., `pause_50_requests`).

    Args:
        counter: RequestCounter instance to check
        retailer: Retailer name for logging (optional)
        config: YAML config dict with pause settings (optional, overrides defaults)
        pause_50_requests: Pause after this many requests (default: 50)
        pause_50_min: Minimum pause duration in seconds for 50-request pause (default: 30)
        pause_50_max: Maximum pause duration in seconds for 50-request pause (default: 60)
        pause_200_requests: Longer pause after this many requests (default: 200)
        pause_200_min: Minimum pause duration in seconds for 200-request pause (default: 120)
        pause_200_max: Maximum pause duration in seconds for 200-request pause (default: 180)
    """
    # Read from config if provided, otherwise use defaults
    if config:
        pause_50_requests = config.get('pause_50_requests', pause_50_requests)
        pause_50_min = config.get('pause_50_min', pause_50_min)
        pause_50_max = config.get('pause_50_max', pause_50_max)
        pause_200_requests = config.get('pause_200_requests', pause_200_requests)
        pause_200_min = config.get('pause_200_min', pause_200_min)
        pause_200_max = config.get('pause_200_max', pause_200_max)

    # Skip if pauses are effectively disabled
    if pause_50_requests >= PAUSE.DISABLED_THRESHOLD and pause_200_requests >= PAUSE.DISABLED_THRESHOLD:
        return

    count = counter.count
    prefix = f"[{retailer}] " if retailer else ""

    if count % pause_200_requests == 0 and count > 0:
        pause_time = random.uniform(pause_200_min, pause_200_max)
        logging.info(f"{prefix}Long pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
    elif count % pause_50_requests == 0 and count > 0:
        pause_time = random.uniform(pause_50_min, pause_50_max)
        logging.info(f"{prefix}Pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
