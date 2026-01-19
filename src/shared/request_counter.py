"""Shared request counter for tracking requests across scrapers"""

import logging
import random
import threading
import time


class RequestCounter:
    """Thread-safe request counter for tracking requests across scrapers.

    Uses a threading lock to ensure atomic increment operations when
    multiple scrapers run concurrently.
    """

    def __init__(self):
        self._count = 0
        self._lock = threading.Lock()

    @property
    def count(self) -> int:
        """Get current count (thread-safe read)"""
        with self._lock:
            return self._count

    def increment(self) -> int:
        """Increment counter and return current count (thread-safe)"""
        with self._lock:
            self._count += 1
            return self._count

    def reset(self) -> None:
        """Reset counter (thread-safe)"""
        with self._lock:
            self._count = 0

    def get_count(self) -> int:
        """Get current count without incrementing (thread-safe)"""
        with self._lock:
            return self._count


def check_pause_logic(
    counter: RequestCounter,
    pause_50_requests: int = 50,
    pause_50_min: float = 30,
    pause_50_max: float = 60,
    pause_200_requests: int = 200,
    pause_200_min: float = 120,
    pause_200_max: float = 180,
) -> None:
    """Check if we need to pause based on request count

    Args:
        counter: RequestCounter instance to check
        pause_50_requests: Pause after this many requests
        pause_50_min: Minimum pause duration for 50-request pause
        pause_50_max: Maximum pause duration for 50-request pause
        pause_200_requests: Longer pause after this many requests
        pause_200_min: Minimum pause duration for 200-request pause
        pause_200_max: Maximum pause duration for 200-request pause
    """
    count = counter.count

    if count % pause_200_requests == 0 and count > 0:
        pause_time = random.uniform(pause_200_min, pause_200_max)
        logging.info(f"Long pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
    elif count % pause_50_requests == 0 and count > 0:
        pause_time = random.uniform(pause_50_min, pause_50_max)
        logging.info(f"Pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
