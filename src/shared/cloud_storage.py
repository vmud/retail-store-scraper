"""
Cloud Storage Integration for Multi-Retailer Store Scraper

Provides pluggable cloud storage support for backing up scraped data.
Currently supports:
- Google Cloud Storage (GCS)

Additional providers can be added by subclassing CloudStorageProvider.
"""

import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


__all__ = [
    'CloudStorageManager',
    'CloudStorageProvider',
    'GCSProvider',
    'GCS_AVAILABLE',
    'get_cloud_storage',
]


try:
    from google.cloud import storage
    from google.cloud.exceptions import GoogleCloudError
    from google.cloud.exceptions import GoogleCloudError
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False


class CloudStorageProvider(ABC):
    """Abstract base class for cloud storage providers."""

    @abstractmethod
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload a file to cloud storage.

        Args:
            local_path: Path to local file
            remote_path: Destination path in cloud storage

        Returns:
            True if upload was successful, False otherwise
        """
        pass

    @abstractmethod
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file from cloud storage.

        Args:
            remote_path: Path in cloud storage
            local_path: Destination path on local filesystem

        Returns:
            True if download was successful, False otherwise
        """
        pass

    @abstractmethod
    def validate_credentials(self) -> Tuple[bool, str]:
        """Validate cloud storage credentials.

        Returns:
            Tuple of (success, message)
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass


class GCSProvider(CloudStorageProvider):
    """Google Cloud Storage provider.

    Requires:
    - google-cloud-storage package
    - Service account key file (GCS_SERVICE_ACCOUNT_KEY env var)
    - Bucket name (GCS_BUCKET_NAME env var)
    """

    def __init__(
        self,
        bucket_name: str,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        """Initialize GCS provider.

        Args:
            bucket_name: GCS bucket name
            project_id: GCP project ID (optional, auto-detected from credentials)
            credentials_path: Path to service account key JSON file
            max_retries: Maximum retry attempts for transient errors
            retry_delay: Base delay between retries (exponential backoff)
        """
        if not GCS_AVAILABLE:
            raise ImportError(
                "google-cloud-storage package required. "
                "Install with: pip install google-cloud-storage"
            )

        self.bucket_name = bucket_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Initialize client with credentials
        if credentials_path:
            self._client = storage.Client.from_service_account_json(
                credentials_path,
                project=project_id
            )
        else:
            self._client = storage.Client(project=project_id)

        self._bucket = self._client.bucket(bucket_name)

    @property
    def name(self) -> str:
        return "GCS"

    def _retry_with_backoff(self, operation, *args, **kwargs) -> Tuple[bool, Any]:
        """Execute operation with exponential backoff retry.

        Args:
            operation: Callable to execute
            *args, **kwargs: Arguments to pass to operation

        Returns:
            Tuple of (success, result_or_error)
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                result = operation(*args, **kwargs)
                return True, result
            except GoogleCloudError as e:
                last_error = e
                # Don't retry on permission errors (4xx)
                if hasattr(e, 'code') and 400 <= e.code < 500:
                    logging.warning(f"GCS client error (not retrying): {e}")
                    return False, str(e)

                # Only sleep if there are more attempts remaining
                if attempt < self.max_retries - 1:
                    # Exponential backoff: 2s, 4s, 8s
                    wait_time = self.retry_delay * (2 ** attempt)
                    logging.warning(
                        f"GCS transient error (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    time.sleep(wait_time)
                else:
                    logging.warning(
                        f"GCS transient error (attempt {attempt + 1}/{self.max_retries}), "
                        f"no more retries: {e}"
                    )

        return False, str(last_error) if last_error else "Unknown error"

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload a file to GCS bucket.

        Args:
            local_path: Path to local file
            remote_path: Destination blob name in bucket

        Returns:
            True if upload was successful
        """
        if not os.path.exists(local_path):
            logging.error(f"Local file not found: {local_path}")
            return False

        def _upload():
            blob = self._bucket.blob(remote_path)
            blob.upload_from_filename(local_path)
            return True

        success, result = self._retry_with_backoff(_upload)

        if success:
            logging.info(f"Uploaded {local_path} -> gs://{self.bucket_name}/{remote_path}")
        else:
            logging.error(f"Failed to upload {local_path}: {result}")

        return success

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file from GCS bucket.

        Args:
            remote_path: Blob name in bucket
            local_path: Destination path on local filesystem

        Returns:
            True if download was successful
        """
        # Ensure parent directory exists
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        def _download():
            blob = self._bucket.blob(remote_path)
            blob.download_to_filename(local_path)
            return True

        success, result = self._retry_with_backoff(_download)

        if success:
            logging.info(f"Downloaded gs://{self.bucket_name}/{remote_path} -> {local_path}")
        else:
            logging.error(f"Failed to download {remote_path}: {result}")

        return success

    def validate_credentials(self) -> Tuple[bool, str]:
        """Validate GCS credentials by listing bucket contents.

        Returns:
            Tuple of (success, message)
        """
        try:
            # Try to access bucket metadata to validate credentials
            self._bucket.reload()
            return True, f"GCS credentials valid for bucket: {self.bucket_name}"
        except GoogleCloudError as e:
            return False, f"GCS credential validation failed: {e}"


class CloudStorageManager:
    """Manager for uploading scraped data to cloud storage."""

    def __init__(self, provider: CloudStorageProvider, enable_history: bool = False):
        """Initialize cloud storage manager.

        Args:
            provider: Cloud storage provider instance
            enable_history: If True, also upload timestamped copies to history folder
        """
        self._provider = provider
        self.enable_history = enable_history

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return self._provider.name

    def upload_retailer_data(
        self,
        retailer: str,
        output_dir: str,
        formats: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """Upload retailer data files to cloud storage.

        Args:
            retailer: Retailer name (used as folder prefix)
            output_dir: Local output directory containing export files
            formats: List of format extensions to upload (default: json, csv, xlsx)

        Returns:
            Dictionary mapping file names to upload success status
        """
        if formats is None:
            formats = ['json', 'csv', 'xlsx']

        results = {}
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')

        for fmt in formats:
            local_file = os.path.join(output_dir, f'stores_latest.{fmt}')

            if not os.path.exists(local_file):
                logging.debug(f"Skipping {fmt} (file not found): {local_file}")
                continue

            # Upload to retailer folder (overwrites previous - versioning preserves history)
            remote_path = f"{retailer}/stores_latest.{fmt}"
            success = self._provider.upload_file(local_file, remote_path)
            results[f"stores_latest.{fmt}"] = success

            # Optionally upload timestamped copy to history folder
            if self.enable_history and success:
                history_path = f"history/{retailer}/stores_{timestamp}.{fmt}"
                history_success = self._provider.upload_file(local_file, history_path)
                results[f"history/stores_{timestamp}.{fmt}"] = history_success

        return results

    def validate_credentials(self) -> Tuple[bool, str]:
        """Validate cloud storage credentials.

        Returns:
            Tuple of (success, message)
        """
        return self._provider.validate_credentials()


def get_cloud_storage(
    bucket_override: Optional[str] = None,
    enable_history: Optional[bool] = None,
    config: Optional[Dict[str, Any]] = None
) -> Optional[CloudStorageManager]:
    """Get configured cloud storage manager from environment/config.

    Checks for cloud storage configuration in environment variables:
    - GCS_SERVICE_ACCOUNT_KEY: Path to service account JSON file
    - GCS_BUCKET_NAME: GCS bucket name
    - GCS_PROJECT_ID: GCP project ID (optional)
    - GCS_ENABLE_HISTORY: Enable history uploads (optional, default: false)

    Args:
        bucket_override: Override bucket name from CLI
        enable_history: Override history setting from CLI
        config: YAML config dict (optional, for additional settings)

    Returns:
        CloudStorageManager instance, or None if not configured
    """
    # Check if GCS is configured
    credentials_path = os.environ.get('GCS_SERVICE_ACCOUNT_KEY')
    bucket_name = bucket_override or os.environ.get('GCS_BUCKET_NAME')
    project_id = os.environ.get('GCS_PROJECT_ID')

    # Get history setting (CLI override > env var > config > default)
    if enable_history is None:
        env_history = os.environ.get('GCS_ENABLE_HISTORY', '').lower()
        if env_history in ('true', '1', 'yes'):
            enable_history = True
        elif config and config.get('cloud_storage', {}).get('enable_history'):
            enable_history = True
        else:
            enable_history = False

    # Check for required configuration
    if not bucket_name:
        logging.debug("Cloud storage not configured: GCS_BUCKET_NAME not set")
        return None

    if not credentials_path:
        logging.debug("Cloud storage not configured: GCS_SERVICE_ACCOUNT_KEY not set")
        return None

    if not os.path.exists(credentials_path):
        logging.warning(f"GCS credentials file not found: {credentials_path}")
        return None

    # Get retry settings from config
    max_retries = 3
    retry_delay = 2.0

    if config and 'cloud_storage' in config:
        cs_config = config['cloud_storage']
        max_retries = cs_config.get('max_retries', max_retries)
        retry_delay = cs_config.get('retry_delay', retry_delay)

    try:
        provider = GCSProvider(
            bucket_name=bucket_name,
            project_id=project_id,
            credentials_path=credentials_path,
            max_retries=max_retries,
            retry_delay=retry_delay
        )

        manager = CloudStorageManager(
            provider=provider,
            enable_history=enable_history
        )

        logging.info(f"GCS cloud storage enabled: bucket={bucket_name}, history={enable_history}")
        return manager

    except ImportError as e:
        logging.warning(f"Cloud storage unavailable: {e}")
        return None
    except Exception as e:
        logging.warning(f"Failed to initialize cloud storage: {e}")
        return None
