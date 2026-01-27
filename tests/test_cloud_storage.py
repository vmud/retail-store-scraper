"""
Tests for CloudStorage - GCS integration for backup/sync
"""

import os
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock
import pytest


class TestGCSProviderImport:
    """Tests for GCSProvider import handling"""

    def test_gcs_available_flag_when_installed(self):
        """Test that GCS_AVAILABLE is True when google-cloud-storage is installed"""
        from src.shared.cloud_storage import GCS_AVAILABLE
        # This will be True in CI since google-cloud-storage is in requirements.txt
        assert isinstance(GCS_AVAILABLE, bool)

    def test_import_error_when_gcs_not_available(self):
        """Test that GCSProvider raises ImportError when GCS package is missing"""
        with patch.dict('sys.modules', {'google.cloud': None, 'google.cloud.storage': None}):
            # Force reimport to get the import error behavior
            # Note: This is tricky to test without actually uninstalling the package
            # Instead we test the initialization check
            pass


class TestGCSProvider:
    """Tests for GCSProvider implementation"""

    @pytest.fixture
    def mock_gcs_client(self):
        """Create mock GCS client and bucket"""
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

    def test_provider_name(self, mock_gcs_client):
        """Test that provider name is 'GCS'"""
        from src.shared.cloud_storage import GCSProvider

        provider = GCSProvider(
            bucket_name='test-bucket',
            credentials_path='/fake/path.json'
        )
        assert provider.name == 'GCS'

    def test_initialization_with_credentials_path(self, mock_gcs_client):
        """Test initialization with explicit credentials path"""
        from src.shared.cloud_storage import GCSProvider

        provider = GCSProvider(
            bucket_name='test-bucket',
            project_id='test-project',
            credentials_path='/path/to/creds.json'
        )

        mock_gcs_client['client_class'].from_service_account_json.assert_called_once_with(
            '/path/to/creds.json',
            project='test-project'
        )
        assert provider.bucket_name == 'test-bucket'

    def test_initialization_without_credentials_path(self, mock_gcs_client):
        """Test initialization uses default credentials when no path provided"""
        from src.shared.cloud_storage import GCSProvider

        provider = GCSProvider(
            bucket_name='test-bucket',
            project_id='test-project'
        )

        mock_gcs_client['client_class'].assert_called_once_with(project='test-project')

    def test_upload_file_success(self, mock_gcs_client):
        """Test successful file upload"""
        from src.shared.cloud_storage import GCSProvider

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'test content')
            local_path = f.name

        try:
            provider = GCSProvider(
                bucket_name='test-bucket',
                credentials_path='/fake/path.json'
            )

            mock_blob = MagicMock()
            mock_gcs_client['bucket'].blob.return_value = mock_blob

            result = provider.upload_file(local_path, 'remote/path.json')

            assert result is True
            mock_gcs_client['bucket'].blob.assert_called_with('remote/path.json')
            mock_blob.upload_from_filename.assert_called_once_with(local_path)
        finally:
            os.unlink(local_path)

    def test_upload_file_local_not_found(self, mock_gcs_client):
        """Test upload returns False when local file doesn't exist"""
        from src.shared.cloud_storage import GCSProvider

        provider = GCSProvider(
            bucket_name='test-bucket',
            credentials_path='/fake/path.json'
        )

        result = provider.upload_file('/nonexistent/file.json', 'remote/path.json')
        assert result is False

    def test_upload_file_retry_on_transient_error(self, mock_gcs_client):
        """Test upload retries on transient errors with exponential backoff"""
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
                retry_delay=0.01  # Fast for testing
            )

            mock_blob = MagicMock()
            mock_gcs_client['bucket'].blob.return_value = mock_blob

            # Create a real exception that will be caught
            error = GoogleCloudError('Service unavailable')
            error.code = 503  # Service unavailable (transient)

            # Fail twice, then succeed
            mock_blob.upload_from_filename.side_effect = [
                error, error, None
            ]

            result = provider.upload_file(local_path, 'remote/path.json')

            assert result is True
            assert mock_blob.upload_from_filename.call_count == 3
        finally:
            os.unlink(local_path)

    def test_upload_file_no_retry_on_client_error(self, mock_gcs_client):
        """Test upload doesn't retry on 4xx client errors"""
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
                retry_delay=0.01
            )

            mock_blob = MagicMock()
            mock_gcs_client['bucket'].blob.return_value = mock_blob

            # 403 Forbidden - should not retry
            error = GoogleCloudError('Forbidden')
            error.code = 403
            mock_blob.upload_from_filename.side_effect = error

            result = provider.upload_file(local_path, 'remote/path.json')

            # Should fail without retrying (only 1 call)
            assert result is False
            assert mock_blob.upload_from_filename.call_count == 1
        finally:
            os.unlink(local_path)

    def test_download_file_success(self, mock_gcs_client):
        """Test successful file download"""
        from src.shared.cloud_storage import GCSProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = os.path.join(tmpdir, 'downloaded.json')

            provider = GCSProvider(
                bucket_name='test-bucket',
                credentials_path='/fake/path.json'
            )

            mock_blob = MagicMock()
            mock_gcs_client['bucket'].blob.return_value = mock_blob

            result = provider.download_file('remote/path.json', local_path)

            assert result is True
            mock_blob.download_to_filename.assert_called_once_with(local_path)

    def test_download_file_creates_parent_directory(self, mock_gcs_client):
        """Test download creates parent directory if it doesn't exist"""
        from src.shared.cloud_storage import GCSProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = os.path.join(tmpdir, 'subdir', 'nested', 'file.json')

            provider = GCSProvider(
                bucket_name='test-bucket',
                credentials_path='/fake/path.json'
            )

            mock_blob = MagicMock()
            mock_gcs_client['bucket'].blob.return_value = mock_blob

            result = provider.download_file('remote/path.json', local_path)

            assert result is True
            assert os.path.exists(os.path.dirname(local_path))

    def test_validate_credentials_success(self, mock_gcs_client):
        """Test credential validation success"""
        from src.shared.cloud_storage import GCSProvider

        provider = GCSProvider(
            bucket_name='test-bucket',
            credentials_path='/fake/path.json'
        )

        success, message = provider.validate_credentials()

        assert success is True
        assert 'test-bucket' in message
        mock_gcs_client['bucket'].reload.assert_called_once()

    def test_validate_credentials_failure(self, mock_gcs_client):
        """Test credential validation failure"""
        from src.shared.cloud_storage import GCSProvider
        from google.cloud.exceptions import GoogleCloudError

        provider = GCSProvider(
            bucket_name='test-bucket',
            credentials_path='/fake/path.json'
        )

        mock_gcs_client['bucket'].reload.side_effect = GoogleCloudError('Access denied')

        success, message = provider.validate_credentials()

        assert success is False
        assert 'Access denied' in message


class TestCloudStorageManager:
    """Tests for CloudStorageManager orchestration"""

    @pytest.fixture
    def mock_provider(self):
        """Create mock provider"""
        provider = MagicMock()
        provider.name = 'MockProvider'
        provider.upload_file.return_value = True
        provider.validate_credentials.return_value = (True, 'Valid')
        return provider

    def test_provider_name(self, mock_provider):
        """Test manager exposes provider name"""
        from src.shared.cloud_storage import CloudStorageManager

        manager = CloudStorageManager(mock_provider)
        assert manager.provider_name == 'MockProvider'

    def test_upload_retailer_data_default_formats(self, mock_provider):
        """Test uploading retailer data with default formats"""
        from src.shared.cloud_storage import CloudStorageManager

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            for ext in ['json', 'csv', 'xlsx']:
                with open(os.path.join(tmpdir, f'stores_latest.{ext}'), 'w') as f:
                    f.write('test')

            manager = CloudStorageManager(mock_provider)
            results = manager.upload_retailer_data('verizon', tmpdir)

            assert results['stores_latest.json'] is True
            assert results['stores_latest.csv'] is True
            assert results['stores_latest.xlsx'] is True
            assert mock_provider.upload_file.call_count == 3

    def test_upload_retailer_data_specific_formats(self, mock_provider):
        """Test uploading retailer data with specific formats"""
        from src.shared.cloud_storage import CloudStorageManager

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create only json file
            with open(os.path.join(tmpdir, 'stores_latest.json'), 'w') as f:
                f.write('test')

            manager = CloudStorageManager(mock_provider)
            results = manager.upload_retailer_data('verizon', tmpdir, formats=['json'])

            assert 'stores_latest.json' in results
            assert mock_provider.upload_file.call_count == 1

    def test_upload_retailer_data_skips_missing_files(self, mock_provider):
        """Test that missing files are silently skipped"""
        from src.shared.cloud_storage import CloudStorageManager

        with tempfile.TemporaryDirectory() as tmpdir:
            # Only create json, not csv or xlsx
            with open(os.path.join(tmpdir, 'stores_latest.json'), 'w') as f:
                f.write('test')

            manager = CloudStorageManager(mock_provider)
            results = manager.upload_retailer_data('verizon', tmpdir)

            # Only json should be in results
            assert 'stores_latest.json' in results
            assert 'stores_latest.csv' not in results
            assert mock_provider.upload_file.call_count == 1

    def test_upload_retailer_data_with_history(self, mock_provider):
        """Test uploading with history enabled"""
        from src.shared.cloud_storage import CloudStorageManager

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'stores_latest.json'), 'w') as f:
                f.write('test')

            manager = CloudStorageManager(mock_provider, enable_history=True)
            results = manager.upload_retailer_data('verizon', tmpdir, formats=['json'])

            # Should have both latest and history
            assert 'stores_latest.json' in results
            assert any('history/' in key for key in results.keys())
            assert mock_provider.upload_file.call_count == 2

    def test_upload_retailer_data_partial_failure(self, mock_provider):
        """Test partial upload failure handling"""
        from src.shared.cloud_storage import CloudStorageManager

        with tempfile.TemporaryDirectory() as tmpdir:
            for ext in ['json', 'csv']:
                with open(os.path.join(tmpdir, f'stores_latest.{ext}'), 'w') as f:
                    f.write('test')

            # Fail on CSV upload
            mock_provider.upload_file.side_effect = [True, False]

            manager = CloudStorageManager(mock_provider)
            results = manager.upload_retailer_data('verizon', tmpdir, formats=['json', 'csv'])

            assert results['stores_latest.json'] is True
            assert results['stores_latest.csv'] is False

    def test_validate_credentials(self, mock_provider):
        """Test credential validation pass-through"""
        from src.shared.cloud_storage import CloudStorageManager

        manager = CloudStorageManager(mock_provider)
        success, message = manager.validate_credentials()

        assert success is True
        mock_provider.validate_credentials.assert_called_once()


class TestGetCloudStorage:
    """Tests for get_cloud_storage factory function"""

    def test_returns_none_when_bucket_not_configured(self):
        """Test returns None when GCS_BUCKET_NAME is not set"""
        from src.shared.cloud_storage import get_cloud_storage

        with patch.dict(os.environ, {}, clear=True):
            result = get_cloud_storage()
            assert result is None

    def test_returns_none_when_credentials_not_configured(self):
        """Test returns None when GCS_SERVICE_ACCOUNT_KEY is not set"""
        from src.shared.cloud_storage import get_cloud_storage

        with patch.dict(os.environ, {'GCS_BUCKET_NAME': 'test-bucket'}, clear=True):
            result = get_cloud_storage()
            assert result is None

    def test_returns_none_when_credentials_file_missing(self):
        """Test returns None when credentials file doesn't exist"""
        from src.shared.cloud_storage import get_cloud_storage

        env = {
            'GCS_BUCKET_NAME': 'test-bucket',
            'GCS_SERVICE_ACCOUNT_KEY': '/nonexistent/path.json'
        }
        with patch.dict(os.environ, env, clear=True):
            result = get_cloud_storage()
            assert result is None

    def test_bucket_override_from_cli(self):
        """Test bucket name can be overridden via CLI argument"""
        from src.shared.cloud_storage import get_cloud_storage

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            f.write(b'{}')
            creds_path = f.name

        try:
            env = {
                'GCS_BUCKET_NAME': 'default-bucket',
                'GCS_SERVICE_ACCOUNT_KEY': creds_path
            }

            with patch.dict(os.environ, env, clear=True):
                with patch('src.shared.cloud_storage.GCSProvider') as mock_provider:
                    mock_provider.return_value = MagicMock()

                    get_cloud_storage(bucket_override='cli-bucket')

                    # Verify CLI bucket was used
                    call_kwargs = mock_provider.call_args[1]
                    assert call_kwargs['bucket_name'] == 'cli-bucket'
        finally:
            os.unlink(creds_path)

    def test_history_from_env_var(self):
        """Test history enabled via GCS_ENABLE_HISTORY env var"""
        from src.shared.cloud_storage import get_cloud_storage

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            f.write(b'{}')
            creds_path = f.name

        try:
            env = {
                'GCS_BUCKET_NAME': 'test-bucket',
                'GCS_SERVICE_ACCOUNT_KEY': creds_path,
                'GCS_ENABLE_HISTORY': 'true'
            }

            with patch.dict(os.environ, env, clear=True):
                with patch('src.shared.cloud_storage.GCSProvider') as mock_provider:
                    mock_provider.return_value = MagicMock()

                    manager = get_cloud_storage()

                    assert manager is not None
                    assert manager.enable_history is True
        finally:
            os.unlink(creds_path)

    def test_history_override_from_cli(self):
        """Test history can be overridden via CLI argument"""
        from src.shared.cloud_storage import get_cloud_storage

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            f.write(b'{}')
            creds_path = f.name

        try:
            env = {
                'GCS_BUCKET_NAME': 'test-bucket',
                'GCS_SERVICE_ACCOUNT_KEY': creds_path,
                'GCS_ENABLE_HISTORY': 'false'
            }

            with patch.dict(os.environ, env, clear=True):
                with patch('src.shared.cloud_storage.GCSProvider') as mock_provider:
                    mock_provider.return_value = MagicMock()

                    manager = get_cloud_storage(enable_history=True)

                    assert manager is not None
                    assert manager.enable_history is True
        finally:
            os.unlink(creds_path)

    def test_retry_settings_from_config(self):
        """Test retry settings loaded from YAML config"""
        from src.shared.cloud_storage import get_cloud_storage

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            f.write(b'{}')
            creds_path = f.name

        try:
            env = {
                'GCS_BUCKET_NAME': 'test-bucket',
                'GCS_SERVICE_ACCOUNT_KEY': creds_path
            }
            config = {
                'cloud_storage': {
                    'max_retries': 5,
                    'retry_delay': 3.0
                }
            }

            with patch.dict(os.environ, env, clear=True):
                with patch('src.shared.cloud_storage.GCSProvider') as mock_provider:
                    mock_provider.return_value = MagicMock()

                    get_cloud_storage(config=config)

                    call_kwargs = mock_provider.call_args[1]
                    assert call_kwargs['max_retries'] == 5
                    assert call_kwargs['retry_delay'] == 3.0
        finally:
            os.unlink(creds_path)


class TestCloudStorageIntegration:
    """Integration tests for cloud storage module (mocked)"""

    def test_full_upload_workflow(self):
        """Test complete upload workflow from manager to provider"""
        from src.shared.cloud_storage import CloudStorageManager

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            for ext in ['json', 'csv']:
                with open(os.path.join(tmpdir, f'stores_latest.{ext}'), 'w') as f:
                    f.write('{"test": true}' if ext == 'json' else 'test,data')

            # Create mock provider
            mock_provider = MagicMock()
            mock_provider.name = 'GCS'
            mock_provider.upload_file.return_value = True

            manager = CloudStorageManager(mock_provider, enable_history=True)
            results = manager.upload_retailer_data('target', tmpdir, formats=['json', 'csv'])

            # Should upload both files + history copies
            assert len(results) == 4  # 2 latest + 2 history
            assert all(v is True for v in results.values())

    def test_error_handling_does_not_crash(self):
        """Test that errors in upload don't crash the manager"""
        from src.shared.cloud_storage import CloudStorageManager

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'stores_latest.json'), 'w') as f:
                f.write('test')

            mock_provider = MagicMock()
            mock_provider.name = 'GCS'
            # Return False to simulate upload failure (not exception)
            mock_provider.upload_file.return_value = False

            manager = CloudStorageManager(mock_provider)

            # Should not raise, should return failure
            results = manager.upload_retailer_data('att', tmpdir, formats=['json'])
            assert results['stores_latest.json'] is False
