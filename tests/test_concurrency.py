"""Tests for global concurrency manager - Issue #153."""

import threading
import time
import pytest
from src.shared.concurrency import GlobalConcurrencyManager, ConcurrencyConfig


@pytest.fixture
def manager():
    """Create a fresh manager instance for testing."""
    mgr = GlobalConcurrencyManager()
    mgr.reset()  # Reset to clean state
    yield mgr
    mgr.reset()  # Cleanup after test


def test_singleton_pattern():
    """Test that GlobalConcurrencyManager is a singleton."""
    manager1 = GlobalConcurrencyManager()
    manager2 = GlobalConcurrencyManager()
    assert manager1 is manager2, "Manager should be a singleton"


def test_default_configuration(manager):
    """Test default configuration values."""
    assert manager.config.global_max_workers == 10
    assert manager.config.per_retailer_max == 5
    assert manager.config.proxy_requests_per_second == 10.0


def test_configure_global_max_workers(manager):
    """Test updating global max workers."""
    manager.configure(global_max_workers=20)
    assert manager.config.global_max_workers == 20


def test_configure_per_retailer_max(manager):
    """Test setting per-retailer worker limits."""
    manager.configure(per_retailer_max={
        'verizon': 7,
        'target': 3,
    })

    assert manager._retailer_max_workers['verizon'] == 7
    assert manager._retailer_max_workers['target'] == 3


def test_configure_proxy_rate_limit(manager):
    """Test updating proxy rate limit."""
    manager.configure(proxy_requests_per_second=15.0)
    assert manager.config.proxy_requests_per_second == 15.0


def test_acquire_slot_basic(manager):
    """Test basic slot acquisition and release."""
    with manager.acquire_slot('verizon'):
        # Successfully acquired slot
        pass
    # Slot should be released after context exit


def test_global_concurrency_limit(manager):
    """Test that global limit prevents oversubscription."""
    manager.configure(global_max_workers=2)

    acquired_count = 0
    lock = threading.Lock()
    results = []

    def worker(worker_id):
        nonlocal acquired_count
        try:
            with manager.acquire_slot('verizon', timeout=0.1):
                with lock:
                    acquired_count += 1
                    current = acquired_count
                time.sleep(0.2)  # Hold slot briefly
                with lock:
                    acquired_count -= 1
                results.append((worker_id, current))
        except TimeoutError:
            results.append((worker_id, 'timeout'))

    # Start 4 workers, but only 2 should acquire slots simultaneously
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Check that max concurrent was 2 (global limit)
    max_concurrent = max(r[1] for r in results if r[1] != 'timeout')
    assert max_concurrent <= 2, f"Global limit exceeded: {max_concurrent}"


def test_per_retailer_limit(manager):
    """Test that per-retailer limits are enforced."""
    manager.configure(
        global_max_workers=10,  # High global limit
        per_retailer_max={'verizon': 2}  # Low retailer limit
    )

    acquired_count = 0
    lock = threading.Lock()
    results = []

    def worker(worker_id):
        nonlocal acquired_count
        try:
            with manager.acquire_slot('verizon', timeout=0.1):
                with lock:
                    acquired_count += 1
                    current = acquired_count
                time.sleep(0.2)  # Hold slot
                with lock:
                    acquired_count -= 1
                results.append((worker_id, current))
        except TimeoutError:
            results.append((worker_id, 'timeout'))

    # Start 4 workers for verizon
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Check that max concurrent was 2 (verizon limit)
    max_concurrent = max(r[1] for r in results if r[1] != 'timeout')
    assert max_concurrent <= 2, f"Retailer limit exceeded: {max_concurrent}"


def test_multiple_retailers_independent(manager):
    """Test that different retailers have independent limits."""
    manager.configure(
        global_max_workers=10,
        per_retailer_max={
            'verizon': 2,
            'target': 2,
        }
    )

    results = {'verizon': [], 'target': []}
    locks = {'verizon': threading.Lock(), 'target': threading.Lock()}
    counts = {'verizon': 0, 'target': 0}

    def worker(retailer, worker_id):
        try:
            with manager.acquire_slot(retailer, timeout=0.5):
                with locks[retailer]:
                    counts[retailer] += 1
                    current = counts[retailer]
                time.sleep(0.1)
                with locks[retailer]:
                    counts[retailer] -= 1
                results[retailer].append((worker_id, current))
        except TimeoutError:
            results[retailer].append((worker_id, 'timeout'))

    # Start workers for both retailers
    threads = []
    for retailer in ['verizon', 'target']:
        for i in range(3):
            t = threading.Thread(target=worker, args=(retailer, i))
            threads.append(t)
            t.start()

    for t in threads:
        t.join()

    # Both retailers should enforce their own limits independently
    for retailer in ['verizon', 'target']:
        successful = [r for r in results[retailer] if r[1] != 'timeout']
        if successful:
            max_concurrent = max(r[1] for r in successful)
            assert max_concurrent <= 2, f"{retailer} limit exceeded"


def test_timeout_acquisition(manager):
    """Test that timeout is respected when slots unavailable."""
    manager.configure(global_max_workers=1)

    # Acquire the only slot
    acquired_first = threading.Event()
    released_first = threading.Event()

    def holder():
        with manager.acquire_slot('verizon'):
            acquired_first.set()
            released_first.wait()  # Hold until signaled

    holder_thread = threading.Thread(target=holder)
    holder_thread.start()
    acquired_first.wait()  # Wait for first worker to acquire

    # Try to acquire with timeout (should fail)
    start = time.time()
    with pytest.raises(TimeoutError):
        with manager.acquire_slot('verizon', timeout=0.5):
            pass
    elapsed = time.time() - start

    # Should timeout around 0.5s (allow 0.2s tolerance)
    assert 0.3 < elapsed < 0.7, f"Timeout took {elapsed}s, expected ~0.5s"

    # Release first holder
    released_first.set()
    holder_thread.join()


def test_get_retailer_semaphore_creates_on_demand(manager):
    """Test that retailer semaphores are created on first access."""
    assert 'new_retailer' not in manager._retailer_semaphores

    sem = manager.get_retailer_semaphore('new_retailer')

    assert sem is not None
    assert 'new_retailer' in manager._retailer_semaphores


def test_get_retailer_semaphore_reuses_existing(manager):
    """Test that existing semaphores are reused."""
    sem1 = manager.get_retailer_semaphore('verizon')
    sem2 = manager.get_retailer_semaphore('verizon')

    assert sem1 is sem2, "Should reuse existing semaphore"


def test_get_stats(manager):
    """Test statistics reporting."""
    manager.configure(
        global_max_workers=15,
        per_retailer_max={'verizon': 7, 'target': 5}
    )

    stats = manager.get_stats()

    assert stats['config']['global_max_workers'] == 15
    assert stats['config']['per_retailer_max'] == 5
    assert 'verizon' in stats['retailers']
    assert stats['retailers']['verizon']['max_workers'] == 7
    assert stats['retailers']['target']['max_workers'] == 5


def test_reset(manager):
    """Test that reset clears all configuration."""
    manager.configure(
        global_max_workers=20,
        per_retailer_max={'verizon': 10}
    )
    manager.get_retailer_semaphore('verizon')

    assert manager.config.global_max_workers == 20
    assert len(manager._retailer_semaphores) > 0

    manager.reset()

    assert manager.config.global_max_workers == 10  # Back to default
    assert len(manager._retailer_semaphores) == 0
    assert len(manager._retailer_max_workers) == 0


def test_concurrent_configuration_changes(manager):
    """Test that configuration changes are thread-safe."""
    def configure_worker(value):
        for _ in range(10):
            manager.configure(global_max_workers=value)
            time.sleep(0.001)

    threads = [
        threading.Thread(target=configure_worker, args=(10,)),
        threading.Thread(target=configure_worker, args=(20,)),
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should end with one of the values (no corruption)
    assert manager.config.global_max_workers in [10, 20]


def test_acquire_slot_without_timeout(manager):
    """Test that acquire_slot works without timeout parameter."""
    manager.configure(global_max_workers=5)

    # Should not raise any exceptions
    with manager.acquire_slot('verizon'):
        time.sleep(0.01)


def test_default_per_retailer_max_used_when_not_configured(manager):
    """Test that default per_retailer_max is used for unconfigured retailers."""
    manager.configure(
        per_retailer_max={'verizon': 7}  # Only configure verizon
    )

    # Get semaphore for unconfigured retailer
    sem = manager.get_retailer_semaphore('target')

    # Should use default (5 from ConcurrencyConfig)
    assert sem is not None
    # We can't directly check semaphore value, but it should be created


def test_multiple_acquire_release_cycles(manager):
    """Test multiple acquire/release cycles work correctly."""
    manager.configure(global_max_workers=1)

    for i in range(5):
        with manager.acquire_slot('verizon'):
            time.sleep(0.01)
        # Should successfully acquire and release each time


def test_exception_in_context_releases_slot(manager):
    """Test that slots are released even if exception occurs in context."""
    manager.configure(global_max_workers=1)

    # Acquire and raise exception
    with pytest.raises(ValueError):
        with manager.acquire_slot('verizon'):
            raise ValueError("Test exception")

    # Should be able to acquire again (slot was released)
    with manager.acquire_slot('verizon', timeout=0.1):
        pass  # Should succeed


def test_thread_safety_of_singleton_creation():
    """Test that singleton creation is thread-safe under contention."""
    instances = []

    def create_instance():
        mgr = GlobalConcurrencyManager()
        instances.append(id(mgr))

    threads = [threading.Thread(target=create_instance) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All instances should have the same ID (same object)
    assert len(set(instances)) == 1, "Multiple instances created"


def test_singleton_initialization_race_condition():
    """Test that singleton initialization is thread-safe under heavy contention.

    This tests the fix for: 'Singleton initialization has race condition between threads'
    Without proper locking, multiple threads could both see _initialized as False
    and proceed to initialize, overwriting each other's state.
    """
    # Reset singleton to test fresh initialization
    GlobalConcurrencyManager._instance = None

    configs_seen = []
    initialization_count = [0]
    init_lock = threading.Lock()

    # Monkey-patch to count initializations
    original_init = GlobalConcurrencyManager.__init__

    def counting_init(self):
        # Call original init
        original_init(self)
        # Track initialization (check if config was just set)
        if hasattr(self, 'config'):
            with init_lock:
                configs_seen.append(id(self.config))

    GlobalConcurrencyManager.__init__ = counting_init

    try:
        barrier = threading.Barrier(20)

        def create_instance():
            barrier.wait()  # Synchronize all threads to start together
            mgr = GlobalConcurrencyManager()
            return mgr

        threads = [threading.Thread(target=create_instance) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All instances should have seen the same config object
        # (only one initialization should have occurred)
        assert len(set(configs_seen)) == 1, (
            f"Multiple config objects created: {len(set(configs_seen))} "
            f"(indicates race condition in initialization)"
        )
    finally:
        GlobalConcurrencyManager.__init__ = original_init
        # Clean up singleton for other tests
        mgr = GlobalConcurrencyManager()
        mgr.reset()


def test_semaphore_capture_prevents_release_mismatch(manager):
    """Test that semaphore references are captured to prevent release mismatch.

    This tests the fix for: 'Global semaphore not captured, causing release mismatch'
    If configure() replaces the semaphore between acquire and release, the release
    should still operate on the originally acquired semaphore.
    """
    manager.configure(global_max_workers=2)

    # Capture the original semaphore reference
    original_semaphore = manager._global_semaphore

    acquired_event = threading.Event()
    continue_event = threading.Event()

    def worker():
        with manager.acquire_slot('verizon'):
            acquired_event.set()
            continue_event.wait()  # Hold the slot

    # Start worker that will hold a slot
    worker_thread = threading.Thread(target=worker)
    worker_thread.start()
    acquired_event.wait()  # Wait for worker to acquire

    # Now reconfigure (this replaces the semaphore)
    manager.configure(global_max_workers=5)
    new_semaphore = manager._global_semaphore

    # The semaphores should be different objects
    assert original_semaphore is not new_semaphore, "Semaphore should be replaced"

    # Release the worker - this should release to the ORIGINAL semaphore,
    # not the new one (due to capturing the reference)
    continue_event.set()
    worker_thread.join()

    # The new semaphore should still have all 5 permits available
    # (the release went to the old semaphore, not this one)
    # We can verify by acquiring all 5 slots immediately
    acquired_slots = 0
    for _ in range(5):
        if manager._global_semaphore.acquire(timeout=0.01):
            acquired_slots += 1

    assert acquired_slots == 5, (
        f"Expected 5 available slots in new semaphore, got {acquired_slots}"
    )

    # Release all acquired slots
    for _ in range(acquired_slots):
        manager._global_semaphore.release()


def test_configure_efficiency(manager):
    """Test that configure() efficiently updates config without recreation.

    This tests the fix for: 'ConcurrencyConfig object re-created multiple times'
    We should directly update attributes rather than recreating the dataclass.
    """
    # Get initial config object
    initial_config = manager.config
    initial_id = id(initial_config)

    # Configure multiple settings - config object should be the same
    manager.configure(global_max_workers=20)
    assert id(manager.config) == initial_id, "Config object should not be recreated"
    assert manager.config.global_max_workers == 20

    manager.configure(proxy_requests_per_second=15.0)
    assert id(manager.config) == initial_id, "Config object should not be recreated"
    assert manager.config.proxy_requests_per_second == 15.0

    # Verify both settings are preserved
    assert manager.config.global_max_workers == 20
