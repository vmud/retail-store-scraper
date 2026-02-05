# Concurrent Testing Patterns

Best practices for testing concurrent code in the retail-store-scraper project.

## Core Principles

### 1. Test Isolation

**Problem**: Tests that modify global state can pollute other tests, especially when testing concurrent access patterns.

**Solution**: Always use try/finally blocks to ensure cleanup, even on test failure:

```python
def test_proxy_client_thread_safety(self):
    """Test that proxy client can be safely accessed from multiple threads."""
    from src.shared.utils import _proxy_clients, _proxy_clients_lock

    try:
        # Test code that modifies global state
        def access_client(retailer_id):
            with _proxy_clients_lock:
                if retailer_id not in _proxy_clients:
                    _proxy_clients[retailer_id] = Mock()
                return _proxy_clients.get(retailer_id)

        # ... thread execution ...

    finally:
        # Clean up test data with lock (prevents race conditions)
        with _proxy_clients_lock:
            test_keys = [k for k in _proxy_clients.keys() if k.startswith('test_')]
            for key in test_keys:
                del _proxy_clients[key]
```

### 2. Explicit Assertions

**Problem**: Silent exception handling (try/except/pass) can mask test failures:

```python
# BAD: Swallows assertion errors
try:
    save_checkpoint(data, checkpoint_file)
except (TypeError, ValueError):
    pass  # Expected behavior
```

**Solution**: Use `pytest.raises()` to explicitly assert exceptions:

```python
# GOOD: Explicitly tests for expected exception
with pytest.raises((TypeError, ValueError)):
    save_checkpoint(data, checkpoint_file)
```

### 3. Thread-Safe Cleanup

**Problem**: Modifying shared data structures without locks can cause race conditions:

```python
# BAD: No lock during cleanup
test_keys = [k for k in _proxy_clients.keys() if k.startswith('retailer_')]
for key in test_keys:
    del _proxy_clients[key]
```

**Solution**: Always acquire locks when accessing shared resources:

```python
# GOOD: Lock held during both iteration and deletion
with _proxy_clients_lock:
    test_keys = [k for k in _proxy_clients.keys() if k.startswith('retailer_')]
    for key in test_keys:
        del _proxy_clients[key]
```

### 4. Mock Ordering

**Problem**: Instantiating objects before mocks are set up can cause tests to interact with real resources:

```python
# BAD: Manager created before mocks
manager = ScraperManager()  # Calls real __init__ with file I/O

with patch('subprocess.Popen') as mock_popen:
    # Too late, __init__ already ran
    manager.start('retailer')
```

**Solution**: Set up all mocks before instantiating the object under test:

```python
# GOOD: Mocks in place before instantiation
with patch('subprocess.Popen') as mock_popen, \
     patch('src.shared.scraper_manager.load_retailers_config') as mock_config, \
     patch('src.shared.scraper_manager.RunTracker'):

    mock_config.return_value = {'retailer': {'enabled': True}}

    # Now safe to instantiate
    manager = ScraperManager()
    manager.start('retailer')
```

### 5. Proper Resource Management

**Problem**: Manual file cleanup with tempfile can leak resources on test failure:

```python
# BAD: Manual cleanup may not run on failure
with tempfile.NamedTemporaryFile(delete=False) as f:
    f.write(b'test content')
    local_path = f.name

try:
    # ... test code ...
finally:
    os.unlink(local_path)  # Easy to forget, may fail if test crashes
```

**Solution**: Use pytest's `tmp_path` fixture for automatic cleanup:

```python
# GOOD: Automatic cleanup by pytest
def test_something(self, tmp_path):
    local_path = tmp_path / "test.txt"
    local_path.write_bytes(b'test content')

    # ... test code ...
    # No cleanup needed - pytest handles it
```

### 6. Meaningful Assertions

**Problem**: Tests without assertions provide no validation:

```python
# BAD: Comment says what should happen, but no assertion
# Should have exactly 3 clients (retailer_0, retailer_1, retailer_2)
# Clean up test data
```

**Solution**: Add explicit assertions for expected behavior:

```python
# GOOD: Assertions verify the expected thread-safe behavior
with _proxy_clients_lock:
    test_keys = [k for k in _proxy_clients.keys() if k.startswith('retailer_')]
    assert len(test_keys) == 3
    assert 'retailer_0' in test_keys
    assert 'retailer_1' in test_keys
    assert 'retailer_2' in test_keys
```

## ThreadPoolExecutor Testing Patterns

### Basic Parallel Execution Test

```python
def test_thread_pool_parallel_execution(self):
    """Test basic ThreadPoolExecutor parallel execution."""
    def worker_task(value):
        time.sleep(0.05)
        return value * 2

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(worker_task, i) for i in range(3)]
        results = [f.result() for f in futures]

    elapsed = time.time() - start_time

    # Should complete in ~0.05s (parallel), not 0.15s (sequential)
    assert elapsed < 0.15
    assert results == [0, 2, 4]
```

### Exception Handling in Workers

```python
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
```

### Mocking ThreadPoolExecutor

```python
def test_mock_thread_pool_executor_pattern(self):
    """Test pattern for mocking ThreadPoolExecutor in unit tests."""
    mock_results = {"task1": "result1", "task2": "result2"}

    def mock_submit(func, *args):
        """Mock submit that returns a mock future."""
        future = Mock(spec=Future)
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
```

## Lock Testing Patterns

### File Write Locks

```python
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

    threads = [
        threading.Thread(target=write_with_lock, args=(i,))
        for i in range(10)
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify all writes completed without corruption
    with open(file_path, 'r') as f:
        lines = f.readlines()

    assert len(lines) == 10
    assert len(results) == 10
```

### Dictionary Access Locks

```python
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
```

## Resource Cleanup Patterns

### Session Cleanup in Finally Blocks

```python
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
```

### Context Manager Cleanup

```python
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
    with pytest.raises(RuntimeError):
        executor.submit(worker_task, 10)
```

## Type Hints Best Practices

Use `Optional` for parameters that can be `None`:

```python
from typing import Optional

def _create_response(
    status_code: int = 200,
    text: str = "",
    json_data: Optional[dict] = None,
    content: Optional[bytes] = None,
    headers: Optional[dict] = None,
    raise_error: Optional[Exception] = None
):
    """Create a mock response object."""
    # ...
```

## Summary Checklist

When writing concurrent tests, ensure:

- [ ] All mocks are set up before object instantiation
- [ ] try/finally blocks used for cleanup of shared state
- [ ] Locks held when accessing/modifying shared data structures
- [ ] Explicit assertions instead of silent exception handling
- [ ] pytest fixtures (tmp_path) used for file operations
- [ ] Assertions verify expected concurrent behavior
- [ ] No broad exception handlers that swallow AssertionError
- [ ] Type hints use Optional for nullable parameters

## Related Files

- `/tests/test_concurrent_execution.py` - Concurrent execution patterns
- `/tests/test_edge_cases.py` - Edge case handling
- `/tests/conftest.py` - Shared test fixtures
- `/tests/test_cloud_storage_advanced.py` - Advanced cloud storage tests
