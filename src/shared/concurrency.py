"""Global concurrency and rate limiting management for scrapers - Issue #153.

This module provides centralized control over concurrency limits across all
scrapers to prevent CPU oversubscription and coordinate proxy rate limits.

The GlobalConcurrencyManager is a thread-safe singleton that manages:
- Global max workers limit across all scrapers
- Per-retailer worker limits
- Proxy request rate limiting

Usage:
    from src.shared.concurrency import GlobalConcurrencyManager

    manager = GlobalConcurrencyManager()
    with manager.acquire_slot('verizon'):
        # Make request within concurrency limits
        response = session.get(url)
"""

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Optional


__all__ = [
    'ConcurrencyConfig',
    'GlobalConcurrencyManager',
]


@dataclass
class ConcurrencyConfig:
    """Configuration for global concurrency limits.

    Attributes:
        global_max_workers: Maximum concurrent workers across all retailers
        per_retailer_max: Default max workers per retailer (can be overridden)
        proxy_requests_per_second: Rate limit for proxy requests (tokens/sec)
    """

    global_max_workers: int = 10
    per_retailer_max: int = 5
    proxy_requests_per_second: float = 10.0


class GlobalConcurrencyManager:
    """Thread-safe singleton for managing concurrency across all scrapers.

    This manager prevents resource oversubscription by coordinating:
    1. Global worker limit across all retailers
    2. Per-retailer worker limits
    3. Proxy request rate limiting (future enhancement)

    The manager uses semaphores for worker limits and token bucket algorithm
    for rate limiting (future implementation).

    Example:
        manager = GlobalConcurrencyManager()

        # Configure limits (typically from retailers.yaml)
        manager.configure(
            global_max_workers=10,
            per_retailer_max={'verizon': 5, 'target': 3}
        )

        # Acquire slot before making request
        with manager.acquire_slot('verizon'):
            response = session.get(url)
    """

    _instance: Optional['GlobalConcurrencyManager'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'GlobalConcurrencyManager':
        """Create or return singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the manager (only runs once for singleton).

        Thread-safety note: We use the class-level lock to protect initialization
        to prevent race conditions where multiple threads could simultaneously
        see _initialized as False and proceed to overwrite each other's state.
        """
        # Fast path: already initialized (no lock needed)
        # pylint: disable=access-member-before-definition
        # Note: _initialized is set in __new__ before __init__ is called
        if self._initialized:
            return

        # Slow path: need to check under lock to prevent race condition
        with self._lock:
            # Double-check after acquiring lock
            if self._initialized:
                return
            # pylint: enable=access-member-before-definition

            self.config = ConcurrencyConfig()
            self._global_semaphore = threading.Semaphore(self.config.global_max_workers)
            self._retailer_semaphores: Dict[str, threading.Semaphore] = {}
            self._retailer_max_workers: Dict[str, int] = {}
            self._config_lock = threading.Lock()
            self._initialized = True

            logging.debug(
                f"[ConcurrencyManager] Initialized with "
                f"global_max={self.config.global_max_workers}, "
                f"per_retailer_max={self.config.per_retailer_max}"
            )

    def configure(
        self,
        global_max_workers: Optional[int] = None,
        per_retailer_max: Optional[Dict[str, int]] = None,
        proxy_requests_per_second: Optional[float] = None
    ) -> None:
        """Configure concurrency limits (can be called multiple times).

        Args:
            global_max_workers: Maximum concurrent workers across all retailers
            per_retailer_max: Dict mapping retailer names to their max workers
            proxy_requests_per_second: Rate limit for proxy requests

        Note:
            Changing limits while scrapers are running may not take effect
            until currently held slots are released. When the global semaphore
            is replaced, workers holding the old semaphore will release to
            the old instance, and new workers will acquire from the new one.

        Warning:
            Avoid calling configure() while workers are actively holding slots,
            as this replaces semaphores and may cause permit leaks. The
            acquire_slot() method captures semaphore references to ensure
            acquire and release operate on the same semaphore instance.
        """
        with self._config_lock:
            if global_max_workers is not None:
                old_value = self.config.global_max_workers
                # Update config attribute directly (more efficient than recreating)
                self.config.global_max_workers = global_max_workers
                self._global_semaphore = threading.Semaphore(global_max_workers)
                logging.info(
                    f"[ConcurrencyManager] Updated global_max_workers: "
                    f"{old_value} -> {global_max_workers}"
                )

            if per_retailer_max is not None:
                self._retailer_max_workers.update(per_retailer_max)
                # Recreate semaphores for updated retailers
                for retailer, max_workers in per_retailer_max.items():
                    # Fall back to default if None value in config
                    effective_max_workers = (
                        max_workers if max_workers is not None
                        else self.config.per_retailer_max
                    )
                    self._retailer_semaphores[retailer] = threading.Semaphore(effective_max_workers)
                    logging.debug(
                        f"[ConcurrencyManager] Set {retailer} max_workers={effective_max_workers}"
                    )

            if proxy_requests_per_second is not None:
                old_value = self.config.proxy_requests_per_second
                # Update config attribute directly (more efficient than recreating)
                self.config.proxy_requests_per_second = proxy_requests_per_second
                logging.info(
                    f"[ConcurrencyManager] Updated proxy rate limit: "
                    f"{old_value} -> {proxy_requests_per_second} req/s"
                )

    def get_retailer_semaphore(self, retailer: str) -> threading.Semaphore:
        """Get or create per-retailer semaphore.

        Args:
            retailer: Retailer name (e.g., 'verizon', 'target')

        Returns:
            Threading semaphore for the retailer
        """
        if retailer not in self._retailer_semaphores:
            with self._config_lock:
                # Double-check after acquiring lock
                if retailer not in self._retailer_semaphores:
                    max_workers = self._retailer_max_workers.get(
                        retailer,
                        self.config.per_retailer_max
                    )
                    # Fall back to default if None value in config
                    effective_max_workers = (
                        max_workers if max_workers is not None
                        else self.config.per_retailer_max
                    )
                    self._retailer_semaphores[retailer] = threading.Semaphore(effective_max_workers)
                    logging.debug(
                        f"[ConcurrencyManager] Created semaphore for {retailer} "
                        f"with max_workers={effective_max_workers}"
                    )
        return self._retailer_semaphores[retailer]

    @contextmanager
    def acquire_slot(self, retailer: str, timeout: Optional[float] = None):
        """Acquire a global + retailer-specific concurrency slot.

        This context manager acquires both a global slot and a retailer-specific
        slot, ensuring coordinated limits across all scrapers.

        Args:
            retailer: Retailer name (e.g., 'verizon', 'target')
            timeout: Optional timeout in seconds for acquiring slots

        Yields:
            None (the context is active while slots are held)

        Raises:
            TimeoutError: If slots cannot be acquired within timeout

        Example:
            with manager.acquire_slot('verizon', timeout=30):
                response = session.get(url)

        Thread-safety note:
            We capture semaphore references in local variables to ensure that
            acquire and release operate on the same semaphore instance, even if
            configure() replaces the semaphore between acquire and release.
        """
        # Capture semaphore references to ensure acquire/release operate on same instance
        # This prevents permit leaks if configure() replaces semaphores mid-operation
        global_sem = self._global_semaphore
        retailer_sem = self.get_retailer_semaphore(retailer)
        start_time = time.time()

        # Acquire global slot first
        if timeout is not None:
            global_acquired = global_sem.acquire(timeout=timeout)
            if not global_acquired:
                raise TimeoutError(
                    f"[{retailer}] Failed to acquire global slot within {timeout}s"
                )
        else:
            global_sem.acquire()

        try:
            # Acquire retailer slot
            if timeout is not None:
                elapsed = time.time() - start_time
                remaining = max(0, timeout - elapsed)
                retailer_acquired = retailer_sem.acquire(timeout=remaining)
                if not retailer_acquired:
                    raise TimeoutError(
                        f"[{retailer}] Failed to acquire retailer slot within {remaining:.1f}s"
                    )
            else:
                retailer_sem.acquire()

            try:
                yield
            finally:
                retailer_sem.release()
        finally:
            global_sem.release()

    def get_stats(self) -> Dict[str, any]:
        """Get current concurrency statistics.

        Returns:
            Dictionary with current semaphore values and configuration
        """
        stats = {
            'config': {
                'global_max_workers': self.config.global_max_workers,
                'per_retailer_max': self.config.per_retailer_max,
                'proxy_requests_per_second': self.config.proxy_requests_per_second,
            },
            'retailers': {},
        }

        # Note: Semaphore doesn't expose current value in standard library,
        # so we can only report configured limits, not current usage
        for retailer, semaphore in self._retailer_semaphores.items():
            max_workers = self._retailer_max_workers.get(
                retailer,
                self.config.per_retailer_max
            )
            # Fall back to default if None value in config
            effective_max_workers = (
                max_workers if max_workers is not None
                else self.config.per_retailer_max
            )
            stats['retailers'][retailer] = {
                'max_workers': effective_max_workers,
            }

        return stats

    def reset(self) -> None:
        """Reset the manager to initial state (primarily for testing).

        Warning:
            Do not call this while scrapers are actively running, as it
            will recreate semaphores and may cause unpredictable behavior.
        """
        with self._config_lock:
            self.config = ConcurrencyConfig()
            self._global_semaphore = threading.Semaphore(self.config.global_max_workers)
            self._retailer_semaphores.clear()
            self._retailer_max_workers.clear()
            logging.debug("[ConcurrencyManager] Reset to initial state")
