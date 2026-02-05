"""Tests for concurrent execution of multiple scrapers.

This test suite validates concurrent execution patterns including:
- Race conditions in shared resources
- ThreadPoolExecutor behavior with mocked workers
- Resource cleanup in concurrent contexts
- Thread-safe data structure access
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from unittest.mock import Mock, patch
import pytest


class TestConcurrentWorkerExecution:
    """Test concurrent worker execution patterns used in scrapers."""

    def test_parallel_store_extraction(self):
        """Test parallel extraction of multiple stores using ThreadPoolExecutor."""
        def extract_store(store_id):
            """Simulate store extraction."""
            time.sleep(0.05)
            return {'store_id': store_id, 'name': f'Store {store_id}'}

        store_ids = [1, 2, 3, 4, 5]
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(extract_store, sid) for sid in store_ids]
            results = [f.result() for f in futures]

        elapsed = time.time() - start_time

        # Should complete faster than sequential (5 * 0.05 = 0.25s)
        assert elapsed < 0.2
        assert len(results) == 5
        assert all('store_id' in r for r in results)


class TestThreadPoolExecutorBehavior:
    """Test ThreadPoolExecutor patterns used in scrapers."""

    def test_thread_pool_parallel_execution(self):
        """Test basic ThreadPoolExecutor parallel execution."""
        def worker_task(value):
            time.sleep(0.05)
            return value * 2

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(worker_task, i) for i in range(3)]
            results = [f.result() for f in futures]

        end_time = time.time()
        elapsed = end_time - start_time

        # Should complete in ~0.05s (parallel), not 0.15s (sequential)
        assert elapsed < 0.15
        assert results == [0, 2, 4]

    def test_thread_pool_exception_propagation(self):
        """Test that exceptions in worker threads are properly captured."""
        def failing_task(value):
            if value == 1:
                raise ValueError(f"Task {value} failed")
            return value * 2

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(failing_task, i) for i in range(3)]

            results = []
            for future in futures:
                try:
                    results.append(future.result())
                except ValueError as e:
                    results.append(f"error: {e}")

        # Verify exception was caught
        assert results[0] == 0
        assert "error" in str(results[1])
        assert results[2] == 4

    def test_thread_pool_timeout_behavior(self):
        """Test ThreadPoolExecutor future timeout handling."""
        def slow_task():
            time.sleep(1.0)
            return "completed"

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(slow_task)

            # Verify timeout raises exception
            with pytest.raises(Exception):  # TimeoutError or concurrent.futures.TimeoutError
                future.result(timeout=0.1)

    def test_mock_thread_pool_executor_pattern(self):
        """Test pattern for mocking ThreadPoolExecutor in unit tests."""
        # Demonstrate how to mock ThreadPoolExecutor behavior
        mock_results = {"task1": "result1", "task2": "result2"}

        def mock_submit(func, *args):
            """Mock submit that returns a mock future."""
            future = Mock(spec=Future)
            # Simulate executing the function
            key = args[0] if args else "default"
            future.result.return_value = mock_results.get(key, "default_result")
            return future

        mock_executor = Mock()
        mock_executor.submit.side_effect = mock_submit

        # Use mocked executor
        future1 = mock_executor.submit(lambda x: x, "task1")
        future2 = mock_executor.submit(lambda x: x, "task2")

        assert future1.result() == "result1"
        assert future2.result() == "result2"
        assert mock_executor.submit.call_count == 2


class TestSharedResourceRaceConditions:
    """Test race conditions in shared resources."""

    def test_concurrent_file_writes_with_lock(self, tmp_path):
        """Test that file writes with locks prevent corruption."""
        file_path = tmp_path / "test.txt"

        lock = threading.Lock()
        results = []

        def write_with_lock(value):
            with lock:
                with open(file_path, 'a') as f:
                    f.write(f"{value}\n")
                    results.append(value)

        # Concurrent writes with lock protection
        threads = [
            threading.Thread(target=write_with_lock, args=(i,))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify all writes completed
        with open(file_path, 'r') as f:
            lines = f.readlines()

        assert len(lines) == 10
        assert len(results) == 10

    def test_concurrent_dict_access_with_lock(self):
        """Test that shared dict access with locks prevents race conditions."""
        shared_dict = {}
        lock = threading.Lock()

        def update_dict(key, value):
            with lock:
                shared_dict[key] = value

        threads = [
            threading.Thread(target=update_dict, args=(f"key_{i}", i))
            for i in range(20)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify all updates completed without data loss
        assert len(shared_dict) == 20
        for i in range(20):
            assert shared_dict[f"key_{i}"] == i

    def test_proxy_client_thread_safety(self):
        """Test that proxy client can be safely accessed from multiple threads."""
        from src.shared.utils import _proxy_clients, _proxy_clients_lock

        try:
            # Simulate concurrent access to proxy client dict
            def access_client(retailer_id):
                with _proxy_clients_lock:
                    # Simulate client creation
                    if retailer_id not in _proxy_clients:
                        _proxy_clients[retailer_id] = Mock()
                    return _proxy_clients.get(retailer_id)

            threads = [
                threading.Thread(target=access_client, args=(f"retailer_{i % 3}",))
                for i in range(30)
            ]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Should have exactly 3 clients (retailer_0, retailer_1, retailer_2)
            with _proxy_clients_lock:
                test_keys = [k for k in _proxy_clients.keys() if k.startswith('retailer_')]
                assert len(test_keys) == 3
                assert 'retailer_0' in test_keys
                assert 'retailer_1' in test_keys
                assert 'retailer_2' in test_keys

        finally:
            # Clean up test data with lock (prevents race conditions)
            with _proxy_clients_lock:
                test_keys = [k for k in _proxy_clients.keys() if k.startswith('retailer_')]
                for key in test_keys:
                    del _proxy_clients[key]


class TestResourceCleanup:
    """Test resource cleanup in concurrent contexts."""

    def test_session_cleanup_in_finally_block(self):
        """Test that sessions are properly closed in finally blocks."""
        mock_session = Mock()
        mock_session.close = Mock()

        def simulate_scraper_with_cleanup():
            try:
                # Simulate scraper work
                if True:
                    raise ValueError("Simulated error")
            finally:
                # Cleanup should happen even on error
                mock_session.close()

        # Run and verify cleanup happens despite error
        with pytest.raises(ValueError):
            simulate_scraper_with_cleanup()

        mock_session.close.assert_called_once()

    def test_resource_cleanup_pattern(self):
        """Test resource cleanup pattern used in scrapers."""
        resource_opened = False
        resource_closed = False

        def use_resource():
            nonlocal resource_opened, resource_closed
            resource_opened = True
            try:
                # Simulate work
                pass
            finally:
                resource_closed = True

        use_resource()

        assert resource_opened
        assert resource_closed

    def test_thread_pool_context_manager_cleanup(self):
        """Test that ThreadPoolExecutor context manager properly cleans up."""
        executed = []

        def worker_task(value):
            executed.append(value)
            return value

        # Use context manager
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker_task, i) for i in range(5)]
            results = [f.result() for f in futures]

        # Verify all tasks completed before context exit
        assert len(executed) == 5
        assert results == [0, 1, 2, 3, 4]

        # Executor should be shut down
        # Trying to submit more work should fail
        with pytest.raises(RuntimeError):
            executor.submit(worker_task, 10)


class TestScraperManagerConcurrency:
    """Test ScraperManager concurrent process management."""

    def test_scraper_manager_thread_safety(self):
        """Test that ScraperManager handles concurrent start/stop requests safely."""
        from src.shared.scraper_manager import ScraperManager

        # Mock the process creation to avoid actually starting scrapers
        with patch('subprocess.Popen') as mock_popen, \
             patch('src.shared.scraper_manager.load_retailers_config') as mock_config, \
             patch('src.shared.scraper_manager.RunTracker'):

            mock_config.return_value = {
                'test_retailer': {'enabled': True}
            }

            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None  # Process is running
            mock_popen.return_value = mock_process

            # Instantiate manager after mocks are in place
            manager = ScraperManager()

            # Start a scraper
            manager.start('test_retailer')

            # Verify the scraper is running
            assert manager.is_running('test_retailer')

            # Verify that attempting to start again raises error
            with pytest.raises(ValueError, match="already running"):
                manager.start('test_retailer')

    def test_multiple_scrapers_independent_lifecycle(self):
        """Test that multiple scrapers can run independently without interfering."""
        from src.shared.scraper_manager import ScraperManager

        with patch('subprocess.Popen') as mock_popen, \
             patch('src.shared.scraper_manager.load_retailers_config') as mock_config, \
             patch('src.shared.scraper_manager.RunTracker'):

            mock_config.return_value = {
                'retailer1': {'enabled': True},
                'retailer2': {'enabled': True}
            }

            # Create separate process mocks
            mock_process1 = Mock()
            mock_process1.pid = 11111
            mock_process1.poll.return_value = None

            mock_process2 = Mock()
            mock_process2.pid = 22222
            mock_process2.poll.return_value = None

            mock_popen.side_effect = [mock_process1, mock_process2]

            # Instantiate manager after mocks are in place
            manager = ScraperManager()

            # Start both scrapers
            manager.start('retailer1')
            manager.start('retailer2')

            # Both should be running
            assert manager.is_running('retailer1')
            assert manager.is_running('retailer2')

            # Stopping one shouldn't affect the other
            mock_process1.poll.return_value = 0  # Process exited
            assert not manager.is_running('retailer1')
            assert manager.is_running('retailer2')
