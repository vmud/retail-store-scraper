"""Advanced tests for cloud storage with mocked GCS.

This test suite provides additional coverage for:
- Retry logic with transient failures
- Error handling edge cases
- Concurrent upload scenarios
- Network timeout handling
- Credential validation edge cases
"""

import os
import tempfile
import time
import threading
from unittest.mock import MagicMock, patch, Mock, call
from concurrent.futures import ThreadPoolExecutor
import pytest


class TestGCSRetryLogic:
    """Test GCS provider retry logic with various failure scenarios."""

    @pytest.fixture
    def mock_gcs_client(self):
        """Create mock GCS client and bucket."""
        try:
            import google.cloud.storage
        except ImportError:
            pytest.skip("google-cloud-storage not installed")

        with patch('google.cloud.storage.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_client_class.from_service_account_json.return_value = mock_client
            mock_client_class.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            yield {
                'client_class': mock_client_class,
                'client': mock_client,
                'bucket': mock_bucket
            }

    def test_retry_with_exponential_backoff_timing(self, mock_gcs_client):
        """Test that retry delays follow exponential backoff pattern."""
        from src.shared.cloud_storage import GCSProvider
        from google.cloud.exceptions import GoogleCloudError

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'test content')
            local_path = f.name

        try:
            provider = GCSProvider(
                bucket_name='test-bucket',
                credentials_path='/fake/path.json',
                max_retries=3,
                retry_delay=0.1  # Short delay for testing
            )

            mock_blob = MagicMock()
            mock_gcs_client['bucket'].blob.return_value = mock_blob

            # Create transient error (503 Service Unavailable)
            error = GoogleCloudError('Service unavailable')
            error.code = 503
            mock_blob.upload_from_filename.side_effect = error

            start_time = time.time()

            with patch('time.sleep') as mock_sleep:
                result = provider.upload_file(local_path, 'remote/path.json')

                # Verify exponential backoff: 0.1s, 0.2s (total 2 sleeps for 3 attempts)
                assert mock_sleep.call_count == 2
                calls = mock_sleep.call_args_list
                assert calls[0][0][0] == 0.1  # First retry: 0.1 * 2^0
                assert calls[1][0][0] == 0.2  # Second retry: 0.1 * 2^1

            assert result is False
            assert mock_blob.upload_from_filename.call_count == 3

        finally:
            os.unlink(local_path)

    def test_retry_stops_after_success(self, mock_gcs_client):
        """Test that retries stop immediately after success."""
        from src.shared.cloud_storage import GCSProvider
        from google.cloud.exceptions import GoogleCloudError

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'test content')
            local_path = f.name

        try:
            provider = GCSProvider(
                bucket_name='test-bucket',
                credentials_path='/fake/path.json',
                max_retries=5,
                retry_delay=0.1
            )

            mock_blob = MagicMock()
            mock_gcs_client['bucket'].blob.return_value = mock_blob

            error = GoogleCloudError('Temporary error')
            error.code = 503

            # Fail twice, then succeed
            mock_blob.upload_from_filename.side_effect = [error, error, None]

            with patch('time.sleep'):
                result = provider.upload_file(local_path, 'remote/path.json')

            assert result is True
            # Should only call 3 times (2 failures + 1 success), not all 5 retries
            assert mock_blob.upload_from_filename.call_count == 3

        finally:
            os.unlink(local_path)

    def test_no_retry_on_permanent_errors(self, mock_gcs_client):
        """Test that 4xx errors don't trigger retries."""
        from src.shared.cloud_storage import GCSProvider
        from google.cloud.exceptions import GoogleCloudError

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'test content')
            local_path = f.name

        try:
            provider = GCSProvider(
                bucket_name='test-bucket',
                credentials_path='/fake/path.json',
                max_retries=5,
                retry_delay=0.1
            )

            mock_blob = MagicMock()
            mock_gcs_client['bucket'].blob.return_value = mock_blob

            # 4xx errors (client errors) should not retry
            for error_code in [400, 401, 403, 404]:
                error = GoogleCloudError(f'Client error {error_code}')
                error.code = error_code
                mock_blob.upload_from_filename.side_effect = error
                mock_blob.upload_from_filename.reset_mock()

                result = provider.upload_file(local_path, 'remote/path.json')

                assert result is False
                # Should only try once (no retries)
                assert mock_blob.upload_from_filename.call_count == 1

        finally:
            os.unlink(local_path)

    def test_retry_on_transient_errors(self, mock_gcs_client):
        """Test that 5xx errors trigger retries."""
        from src.shared.cloud_storage import GCSProvider
        from google.cloud.exceptions import GoogleCloudError

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'test content')
            local_path = f.name

        try:
            provider = GCSProvider(
                bucket_name='test-bucket',
                credentials_path='/fake/path.json',
                max_retries=2,
                retry_delay=0.01
            )

            mock_blob = MagicMock()
            mock_gcs_client['bucket'].blob.return_value = mock_blob

            # 5xx errors (server errors) should retry
            for error_code in [500, 502, 503, 504]:
                error = GoogleCloudError(f'Server error {error_code}')
                error.code = error_code
                mock_blob.upload_from_filename.side_effect = error
                mock_blob.upload_from_filename.reset_mock()

                with patch('time.sleep'):
                    result = provider.upload_file(local_path, 'remote/path.json')

                assert result is False
                # Should retry (total attempts = max_retries)
                assert mock_blob.upload_from_filename.call_count == 2

        finally:
            os.unlink(local_path)


class TestGCSErrorHandling:
    """Test GCS error handling edge cases."""

    @pytest.fixture
    def mock_gcs_client(self):
        """Create mock GCS client and bucket."""
        try:
            import google.cloud.storage
        except ImportError:
            pytest.skip("google-cloud-storage not installed")

        with patch('google.cloud.storage.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_client_class.from_service_account_json.return_value = mock_client
            mock_client_class.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            yield {
                'client_class': mock_client_class,
                'client': mock_client,
                'bucket': mock_bucket
            }

    def test_upload_with_no_error_code_attribute(self, mock_gcs_client):
        """Test handling of GoogleCloudError without code attribute."""
        from src.shared.cloud_storage import GCSProvider
        from google.cloud.exceptions import GoogleCloudError

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'test content')
            local_path = f.name

        try:
            provider = GCSProvider(
                bucket_name='test-bucket',
                credentials_path='/fake/path.json',
                max_retries=2,
                retry_delay=0.01
            )

            mock_blob = MagicMock()
            mock_gcs_client['bucket'].blob.return_value = mock_blob

            # Error without code attribute
            error = GoogleCloudError('Generic error')
            # Don't set error.code attribute
            mock_blob.upload_from_filename.side_effect = error

            with patch('time.sleep'):
                result = provider.upload_file(local_path, 'remote/path.json')

            # Should treat as transient and retry
            assert result is False
            assert mock_blob.upload_from_filename.call_count == 2

        finally:
            os.unlink(local_path)

    def test_download_creates_nested_directories(self, mock_gcs_client):
        """Test that download creates deeply nested parent directories."""
        from src.shared.cloud_storage import GCSProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            # Very nested path
            local_path = os.path.join(
                tmpdir, 'level1', 'level2', 'level3', 'level4', 'file.json'
            )

            provider = GCSProvider(
                bucket_name='test-bucket',
                credentials_path='/fake/path.json'
            )

            mock_blob = MagicMock()
            mock_gcs_client['bucket'].blob.return_value = mock_blob

            result = provider.download_file('remote/path.json', local_path)

            assert result is True
            # Verify parent directories were created
            assert os.path.exists(os.path.dirname(local_path))

    def test_download_with_permission_error(self, mock_gcs_client):
        """Test download handling when local directory is not writable."""
        from src.shared.cloud_storage import GCSProvider
        from google.cloud.exceptions import GoogleCloudError

        provider = GCSProvider(
            bucket_name='test-bucket',
            credentials_path='/fake/path.json'
        )

        mock_blob = MagicMock()
        mock_gcs_client['bucket'].blob.return_value = mock_blob

        # Simulate permission error
        error = GoogleCloudError('Permission denied')
        error.code = 403
        mock_blob.download_to_filename.side_effect = error

        result = provider.download_file('remote/path.json', '/tmp/test.json')

        assert result is False

    def test_validate_credentials_with_network_timeout(self, mock_gcs_client):
        """Test credential validation with network timeout."""
        from src.shared.cloud_storage import GCSProvider
        from google.cloud.exceptions import GoogleCloudError

        provider = GCSProvider(
            bucket_name='test-bucket',
            credentials_path='/fake/path.json'
        )

        # Simulate timeout
        mock_gcs_client['bucket'].reload.side_effect = GoogleCloudError('Timeout')

        success, message = provider.validate_credentials()

        assert success is False
        assert 'Timeout' in message


class TestCloudStorageManagerAdvanced:
    """Advanced tests for CloudStorageManager."""

    def test_upload_with_concurrent_formats(self):
        """Test uploading multiple formats concurrently."""
        from src.shared.cloud_storage import CloudStorageManager

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple format files
            for ext in ['json', 'csv', 'xlsx', 'geojson']:
                with open(os.path.join(tmpdir, f'stores_latest.{ext}'), 'w') as f:
                    f.write(f'test {ext} content')

            mock_provider = MagicMock()
            mock_provider.name = 'MockProvider'
            mock_provider.upload_file.return_value = True

            manager = CloudStorageManager(mock_provider)

            # Upload all formats
            results = manager.upload_retailer_data(
                'verizon',
                tmpdir,
                formats=['json', 'csv', 'xlsx', 'geojson']
            )

            # All should succeed
            assert len(results) == 4
            assert all(v is True for v in results.values())
            assert mock_provider.upload_file.call_count == 4

    def test_upload_with_history_failure(self):
        """Test that history upload failure doesn't affect main upload."""
        from src.shared.cloud_storage import CloudStorageManager

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'stores_latest.json'), 'w') as f:
                f.write('{"test": true}')

            mock_provider = MagicMock()
            mock_provider.name = 'GCS'

            # Main upload succeeds, history upload fails
            mock_provider.upload_file.side_effect = [True, False]

            manager = CloudStorageManager(mock_provider, enable_history=True)
            results = manager.upload_retailer_data('att', tmpdir, formats=['json'])

            # Main upload should succeed
            assert results['stores_latest.json'] is True
            # History upload should fail
            history_key = next(k for k in results.keys() if 'history/' in k)
            assert results[history_key] is False

    def test_upload_handles_missing_directory(self):
        """Test upload when output directory doesn't exist."""
        from src.shared.cloud_storage import CloudStorageManager

        mock_provider = MagicMock()
        mock_provider.name = 'GCS'

        manager = CloudStorageManager(mock_provider)

        # Try to upload from non-existent directory
        results = manager.upload_retailer_data(
            'nonexistent',
            '/totally/fake/directory',
            formats=['json']
        )

        # Should handle gracefully (no files found)
        assert len(results) == 0

    def test_multiple_managers_share_provider(self):
        """Test that multiple managers can share the same provider."""
        from src.shared.cloud_storage import CloudStorageManager

        mock_provider = MagicMock()
        mock_provider.name = 'SharedProvider'
        mock_provider.upload_file.return_value = True

        manager1 = CloudStorageManager(mock_provider)
        manager2 = CloudStorageManager(mock_provider, enable_history=True)

        # Both managers share the same provider
        assert manager1.provider_name == manager2.provider_name
        assert manager1.provider_name == 'SharedProvider'


class TestCloudStorageFactoryFunction:
    """Test get_cloud_storage factory function edge cases."""

    def test_returns_none_when_credentials_file_empty(self):
        """Test that empty credentials file returns None."""
        from src.shared.cloud_storage import get_cloud_storage

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            # Empty file
            creds_path = f.name

        try:
            env = {
                'GCS_BUCKET_NAME': 'test-bucket',
                'GCS_SERVICE_ACCOUNT_KEY': creds_path
            }

            with patch.dict(os.environ, env, clear=True):
                with patch('src.shared.cloud_storage.GCSProvider') as mock_provider:
                    # Simulate initialization failure
                    mock_provider.side_effect = ValueError("Invalid credentials")

                    result = get_cloud_storage()

                    # Should handle error and return None
                    assert result is None

        finally:
            os.unlink(creds_path)

    def test_config_override_for_retry_settings(self):
        """Test that config overrides default retry settings."""
        from src.shared.cloud_storage import get_cloud_storage

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            f.write(b'{"type": "service_account"}')
            creds_path = f.name

        try:
            env = {
                'GCS_BUCKET_NAME': 'test-bucket',
                'GCS_SERVICE_ACCOUNT_KEY': creds_path
            }

            config = {
                'cloud_storage': {
                    'max_retries': 10,
                    'retry_delay': 5.0
                }
            }

            with patch.dict(os.environ, env, clear=True):
                with patch('src.shared.cloud_storage.GCSProvider') as mock_provider:
                    mock_provider.return_value = MagicMock()

                    get_cloud_storage(config=config)

                    # Verify retry settings from config were used
                    call_kwargs = mock_provider.call_args[1]
                    assert call_kwargs['max_retries'] == 10
                    assert call_kwargs['retry_delay'] == 5.0

        finally:
            os.unlink(creds_path)

    def test_bucket_override_takes_precedence(self):
        """Test that bucket_override parameter takes precedence over env var."""
        from src.shared.cloud_storage import get_cloud_storage

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            f.write(b'{"type": "service_account"}')
            creds_path = f.name

        try:
            env = {
                'GCS_BUCKET_NAME': 'env-bucket',
                'GCS_SERVICE_ACCOUNT_KEY': creds_path
            }

            with patch.dict(os.environ, env, clear=True):
                with patch('src.shared.cloud_storage.GCSProvider') as mock_provider:
                    mock_provider.return_value = MagicMock()

                    get_cloud_storage(bucket_override='override-bucket')

                    # Verify override bucket was used
                    call_kwargs = mock_provider.call_args[1]
                    assert call_kwargs['bucket_name'] == 'override-bucket'

        finally:
            os.unlink(creds_path)

    def test_history_enabled_via_various_sources(self):
        """Test history can be enabled via env var, config, or CLI."""
        from src.shared.cloud_storage import get_cloud_storage

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            f.write(b'{"type": "service_account"}')
            creds_path = f.name

        try:
            base_env = {
                'GCS_BUCKET_NAME': 'test-bucket',
                'GCS_SERVICE_ACCOUNT_KEY': creds_path
            }

            # Test 1: Enable via CLI (highest priority)
            with patch.dict(os.environ, base_env, clear=True):
                with patch('src.shared.cloud_storage.GCSProvider') as mock_provider:
                    mock_provider.return_value = MagicMock()

                    manager = get_cloud_storage(enable_history=True)
                    assert manager.enable_history is True

            # Test 2: Enable via env var
            env_with_history = {**base_env, 'GCS_ENABLE_HISTORY': 'true'}
            with patch.dict(os.environ, env_with_history, clear=True):
                with patch('src.shared.cloud_storage.GCSProvider') as mock_provider:
                    mock_provider.return_value = MagicMock()

                    manager = get_cloud_storage()
                    assert manager.enable_history is True

            # Test 3: Enable via config
            config_with_history = {
                'cloud_storage': {'enable_history': True}
            }
            with patch.dict(os.environ, base_env, clear=True):
                with patch('src.shared.cloud_storage.GCSProvider') as mock_provider:
                    mock_provider.return_value = MagicMock()

                    manager = get_cloud_storage(config=config_with_history)
                    assert manager.enable_history is True

        finally:
            os.unlink(creds_path)


class TestConcurrentCloudUploads:
    """Test concurrent cloud storage uploads."""

    def test_concurrent_retailer_uploads(self):
        """Test multiple retailers uploading concurrently."""
        from src.shared.cloud_storage import CloudStorageManager

        mock_provider = MagicMock()
        mock_provider.name = 'ConcurrentProvider'

        # Track upload calls
        upload_calls = []

        def mock_upload(local_path, remote_path):
            upload_calls.append((local_path, remote_path))
            time.sleep(0.01)  # Simulate upload time
            return True

        mock_provider.upload_file.side_effect = mock_upload

        manager = CloudStorageManager(mock_provider)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files for multiple retailers
            retailers = ['verizon', 'att', 'target']
            for retailer in retailers:
                retailer_dir = os.path.join(tmpdir, retailer)
                os.makedirs(retailer_dir)
                with open(os.path.join(retailer_dir, 'stores_latest.json'), 'w') as f:
                    f.write(f'{{"retailer": "{retailer}"}}')

            # Upload concurrently using ThreadPoolExecutor
            def upload_retailer(retailer):
                retailer_dir = os.path.join(tmpdir, retailer)
                return manager.upload_retailer_data(
                    retailer,
                    retailer_dir,
                    formats=['json']
                )

            start_time = time.time()

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [
                    executor.submit(upload_retailer, retailer)
                    for retailer in retailers
                ]
                results = [f.result() for f in futures]

            elapsed = time.time() - start_time

            # Verify all succeeded
            assert len(results) == 3
            assert all('stores_latest.json' in r for r in results)

            # Verify concurrent execution (should be ~0.01s, not 0.03s)
            assert elapsed < 0.05

            # Verify all uploads were called
            assert len(upload_calls) == 3

    def test_thread_safe_provider_access(self):
        """Test that provider can be safely accessed from multiple threads."""
        from src.shared.cloud_storage import CloudStorageManager

        mock_provider = MagicMock()
        mock_provider.name = 'ThreadSafeProvider'
        mock_provider.upload_file.return_value = True

        manager = CloudStorageManager(mock_provider)

        results = []

        def access_provider():
            # Access provider name (thread-safe property access)
            name = manager.provider_name
            results.append(name)

        threads = [
            threading.Thread(target=access_provider)
            for _ in range(20)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should have accessed provider successfully
        assert len(results) == 20
        assert all(name == 'ThreadSafeProvider' for name in results)
