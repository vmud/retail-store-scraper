"""Tests for __all__ exports in shared modules"""

import importlib
import sys
from pathlib import Path


class TestModuleExports:
    """Test that all modules have proper __all__ declarations"""

    def test_utils_has_all(self):
        """src.shared.utils should define __all__"""
        from src.shared import utils
        assert hasattr(utils, '__all__'), "utils module should define __all__"
        assert isinstance(utils.__all__, list), "__all__ should be a list"
        assert len(utils.__all__) > 0, "__all__ should not be empty"

    def test_proxy_client_has_all(self):
        """src.shared.proxy_client should define __all__"""
        from src.shared import proxy_client
        assert hasattr(proxy_client, '__all__'), "proxy_client module should define __all__"
        assert isinstance(proxy_client.__all__, list), "__all__ should be a list"
        assert len(proxy_client.__all__) > 0, "__all__ should not be empty"

    def test_cache_has_all(self):
        """src.shared.cache should define __all__"""
        from src.shared import cache
        assert hasattr(cache, '__all__'), "cache module should define __all__"
        assert isinstance(cache.__all__, list), "__all__ should be a list"
        assert len(cache.__all__) > 0, "__all__ should not be empty"

    def test_export_service_has_all(self):
        """src.shared.export_service should define __all__"""
        from src.shared import export_service
        assert hasattr(export_service, '__all__'), "export_service module should define __all__"
        assert isinstance(export_service.__all__, list), "__all__ should be a list"
        assert len(export_service.__all__) > 0, "__all__ should not be empty"

    def test_notifications_has_all(self):
        """src.shared.notifications should define __all__"""
        from src.shared import notifications
        assert hasattr(notifications, '__all__'), "notifications module should define __all__"
        assert isinstance(notifications.__all__, list), "__all__ should be a list"
        assert len(notifications.__all__) > 0, "__all__ should not be empty"

    def test_status_has_all(self):
        """src.shared.status should define __all__"""
        from src.shared import status
        assert hasattr(status, '__all__'), "status module should define __all__"
        assert isinstance(status.__all__, list), "__all__ should be a list"
        assert len(status.__all__) > 0, "__all__ should not be empty"

    def test_request_counter_has_all(self):
        """src.shared.request_counter should define __all__"""
        from src.shared import request_counter
        assert hasattr(request_counter, '__all__'), "request_counter module should define __all__"
        assert isinstance(request_counter.__all__, list), "__all__ should be a list"
        assert len(request_counter.__all__) > 0, "__all__ should not be empty"

    def test_session_factory_has_all(self):
        """src.shared.session_factory should define __all__"""
        from src.shared import session_factory
        assert hasattr(session_factory, '__all__'), "session_factory module should define __all__"
        assert isinstance(session_factory.__all__, list), "__all__ should be a list"
        assert len(session_factory.__all__) > 0, "__all__ should not be empty"

    def test_cloud_storage_has_all(self):
        """src.shared.cloud_storage should define __all__"""
        from src.shared import cloud_storage
        assert hasattr(cloud_storage, '__all__'), "cloud_storage module should define __all__"
        assert isinstance(cloud_storage.__all__, list), "__all__ should be a list"
        assert len(cloud_storage.__all__) > 0, "__all__ should not be empty"

    def test_run_tracker_has_all(self):
        """src.shared.run_tracker should define __all__"""
        from src.shared import run_tracker
        assert hasattr(run_tracker, '__all__'), "run_tracker module should define __all__"
        assert isinstance(run_tracker.__all__, list), "__all__ should be a list"
        assert len(run_tracker.__all__) > 0, "__all__ should not be empty"

    def test_scraper_manager_has_all(self):
        """src.shared.scraper_manager should define __all__"""
        from src.shared import scraper_manager
        assert hasattr(scraper_manager, '__all__'), "scraper_manager module should define __all__"
        assert isinstance(scraper_manager.__all__, list), "__all__ should be a list"
        assert len(scraper_manager.__all__) > 0, "__all__ should not be empty"

    def test_change_detector_has_all(self):
        """src.change_detector should define __all__"""
        from src import change_detector
        assert hasattr(change_detector, '__all__'), "change_detector module should define __all__"
        assert isinstance(change_detector.__all__, list), "__all__ should be a list"
        assert len(change_detector.__all__) > 0, "__all__ should not be empty"


class TestExportedItemsExist:
    """Test that all items in __all__ actually exist in the module"""

    def test_utils_exports_exist(self):
        """All items in utils.__all__ should exist in the module"""
        from src.shared import utils
        for item in utils.__all__:
            assert hasattr(utils, item), f"utils.__all__ includes '{item}' but it doesn't exist in module"

    def test_proxy_client_exports_exist(self):
        """All items in proxy_client.__all__ should exist in the module"""
        from src.shared import proxy_client
        for item in proxy_client.__all__:
            assert hasattr(proxy_client, item), f"proxy_client.__all__ includes '{item}' but it doesn't exist in module"

    def test_cache_exports_exist(self):
        """All items in cache.__all__ should exist in the module"""
        from src.shared import cache
        for item in cache.__all__:
            assert hasattr(cache, item), f"cache.__all__ includes '{item}' but it doesn't exist in module"

    def test_export_service_exports_exist(self):
        """All items in export_service.__all__ should exist in the module"""
        from src.shared import export_service
        for item in export_service.__all__:
            assert hasattr(export_service, item), f"export_service.__all__ includes '{item}' but it doesn't exist in module"

    def test_notifications_exports_exist(self):
        """All items in notifications.__all__ should exist in the module"""
        from src.shared import notifications
        for item in notifications.__all__:
            assert hasattr(notifications, item), f"notifications.__all__ includes '{item}' but it doesn't exist in module"

    def test_status_exports_exist(self):
        """All items in status.__all__ should exist in the module"""
        from src.shared import status
        for item in status.__all__:
            assert hasattr(status, item), f"status.__all__ includes '{item}' but it doesn't exist in module"

    def test_request_counter_exports_exist(self):
        """All items in request_counter.__all__ should exist in the module"""
        from src.shared import request_counter
        for item in request_counter.__all__:
            assert hasattr(request_counter, item), f"request_counter.__all__ includes '{item}' but it doesn't exist in module"

    def test_session_factory_exports_exist(self):
        """All items in session_factory.__all__ should exist in the module"""
        from src.shared import session_factory
        for item in session_factory.__all__:
            assert hasattr(session_factory, item), f"session_factory.__all__ includes '{item}' but it doesn't exist in module"

    def test_cloud_storage_exports_exist(self):
        """All items in cloud_storage.__all__ should exist in the module"""
        from src.shared import cloud_storage
        for item in cloud_storage.__all__:
            assert hasattr(cloud_storage, item), f"cloud_storage.__all__ includes '{item}' but it doesn't exist in module"

    def test_run_tracker_exports_exist(self):
        """All items in run_tracker.__all__ should exist in the module"""
        from src.shared import run_tracker
        for item in run_tracker.__all__:
            assert hasattr(run_tracker, item), f"run_tracker.__all__ includes '{item}' but it doesn't exist in module"

    def test_scraper_manager_exports_exist(self):
        """All items in scraper_manager.__all__ should exist in the module"""
        from src.shared import scraper_manager
        for item in scraper_manager.__all__:
            assert hasattr(scraper_manager, item), f"scraper_manager.__all__ includes '{item}' but it doesn't exist in module"

    def test_change_detector_exports_exist(self):
        """All items in change_detector.__all__ should exist in the module"""
        from src import change_detector
        for item in change_detector.__all__:
            assert hasattr(change_detector, item), f"change_detector.__all__ includes '{item}' but it doesn't exist in module"


class TestNoPrivateItemsInExports:
    """Test that __all__ doesn't include private (underscore-prefixed) items"""

    def test_utils_no_private_exports(self):
        """utils.__all__ should not include private items"""
        from src.shared import utils
        private_items = [item for item in utils.__all__ if item.startswith('_')]
        assert len(private_items) == 0, f"utils.__all__ should not include private items: {private_items}"

    def test_proxy_client_no_private_exports(self):
        """proxy_client.__all__ should not include private items"""
        from src.shared import proxy_client
        private_items = [item for item in proxy_client.__all__ if item.startswith('_')]
        assert len(private_items) == 0, f"proxy_client.__all__ should not include private items: {private_items}"

    def test_cache_no_private_exports(self):
        """cache.__all__ should not include private items"""
        from src.shared import cache
        private_items = [item for item in cache.__all__ if item.startswith('_')]
        assert len(private_items) == 0, f"cache.__all__ should not include private items: {private_items}"

    def test_export_service_no_private_exports(self):
        """export_service.__all__ should not include private items"""
        from src.shared import export_service
        private_items = [item for item in export_service.__all__ if item.startswith('_')]
        assert len(private_items) == 0, f"export_service.__all__ should not include private items: {private_items}"

    def test_notifications_no_private_exports(self):
        """notifications.__all__ should not include private items"""
        from src.shared import notifications
        private_items = [item for item in notifications.__all__ if item.startswith('_')]
        assert len(private_items) == 0, f"notifications.__all__ should not include private items: {private_items}"

    def test_status_no_private_exports(self):
        """status.__all__ should not include private items"""
        from src.shared import status
        private_items = [item for item in status.__all__ if item.startswith('_')]
        assert len(private_items) == 0, f"status.__all__ should not include private items: {private_items}"

    def test_request_counter_no_private_exports(self):
        """request_counter.__all__ should not include private items"""
        from src.shared import request_counter
        private_items = [item for item in request_counter.__all__ if item.startswith('_')]
        assert len(private_items) == 0, f"request_counter.__all__ should not include private items: {private_items}"

    def test_session_factory_no_private_exports(self):
        """session_factory.__all__ should not include private items"""
        from src.shared import session_factory
        private_items = [item for item in session_factory.__all__ if item.startswith('_')]
        assert len(private_items) == 0, f"session_factory.__all__ should not include private items: {private_items}"

    def test_cloud_storage_no_private_exports(self):
        """cloud_storage.__all__ should not include private items"""
        from src.shared import cloud_storage
        private_items = [item for item in cloud_storage.__all__ if item.startswith('_')]
        assert len(private_items) == 0, f"cloud_storage.__all__ should not include private items: {private_items}"

    def test_run_tracker_no_private_exports(self):
        """run_tracker.__all__ should not include private items"""
        from src.shared import run_tracker
        private_items = [item for item in run_tracker.__all__ if item.startswith('_')]
        assert len(private_items) == 0, f"run_tracker.__all__ should not include private items: {private_items}"

    def test_scraper_manager_no_private_exports(self):
        """scraper_manager.__all__ should not include private items"""
        from src.shared import scraper_manager
        private_items = [item for item in scraper_manager.__all__ if item.startswith('_')]
        assert len(private_items) == 0, f"scraper_manager.__all__ should not include private items: {private_items}"

    def test_change_detector_no_private_exports(self):
        """change_detector.__all__ should not include private items"""
        from src import change_detector
        private_items = [item for item in change_detector.__all__ if item.startswith('_')]
        assert len(private_items) == 0, f"change_detector.__all__ should not include private items: {private_items}"


class TestKeyPublicFunctionsExported:
    """Test that key public functions are included in __all__"""

    def test_utils_key_functions_exported(self):
        """Verify key utils functions are in __all__"""
        from src.shared import utils
        required_exports = [
            'setup_logging', 'get_headers', 'random_delay', 'select_delays',
            'get_with_retry', 'save_checkpoint', 'load_checkpoint',
            'save_to_csv', 'save_to_json', 'validate_store_data', 'validate_stores_batch',
            'ValidationResult', 'get_retailer_proxy_config', 'load_retailer_config',
            'get_proxy_client', 'get_with_proxy', 'create_proxied_session', 'ProxiedSession'
        ]
        for func in required_exports:
            assert func in utils.__all__, f"utils.__all__ should include '{func}'"

    def test_proxy_client_key_classes_exported(self):
        """Verify key proxy_client classes are in __all__"""
        from src.shared import proxy_client
        required_exports = ['ProxyMode', 'ProxyConfig', 'ProxyResponse', 'ProxyClient', 'create_proxy_client']
        for cls in required_exports:
            assert cls in proxy_client.__all__, f"proxy_client.__all__ should include '{cls}'"

    def test_cache_key_classes_exported(self):
        """Verify key cache classes are in __all__"""
        from src.shared import cache
        required_exports = ['URLCache', 'RichURLCache']
        for cls in required_exports:
            assert cls in cache.__all__, f"cache.__all__ should include '{cls}'"

    def test_export_service_key_items_exported(self):
        """Verify key export_service items are in __all__"""
        from src.shared import export_service
        required_exports = ['ExportFormat', 'ExportService', 'sanitize_csv_value', 'parse_format_list']
        for item in required_exports:
            assert item in export_service.__all__, f"export_service.__all__ should include '{item}'"

    def test_notifications_key_items_exported(self):
        """Verify key notifications items are in __all__"""
        from src.shared import notifications
        required_exports = ['NotificationProvider', 'SlackNotifier', 'ConsoleNotifier', 'NotificationManager', 'get_notifier']
        for item in required_exports:
            assert item in notifications.__all__, f"notifications.__all__ should include '{item}'"

    def test_status_key_functions_exported(self):
        """Verify key status functions are in __all__"""
        from src.shared import status
        required_exports = ['load_retailers_config', 'get_checkpoint_path', 'get_retailer_status',
                           'get_all_retailers_status', 'get_progress_status']
        for func in required_exports:
            assert func in status.__all__, f"status.__all__ should include '{func}'"

    def test_request_counter_key_items_exported(self):
        """Verify key request_counter items are in __all__"""
        from src.shared import request_counter
        required_exports = ['RequestCounter', 'check_pause_logic']
        for item in required_exports:
            assert item in request_counter.__all__, f"request_counter.__all__ should include '{item}'"

    def test_session_factory_key_functions_exported(self):
        """Verify key session_factory functions are in __all__"""
        from src.shared import session_factory
        required_exports = ['create_session_factory']
        for func in required_exports:
            assert func in session_factory.__all__, f"session_factory.__all__ should include '{func}'"

    def test_cloud_storage_key_items_exported(self):
        """Verify key cloud_storage items are in __all__"""
        from src.shared import cloud_storage
        required_exports = ['CloudStorageProvider', 'GCSProvider', 'CloudStorageManager', 'get_cloud_storage']
        for item in required_exports:
            assert item in cloud_storage.__all__, f"cloud_storage.__all__ should include '{item}'"

    def test_run_tracker_key_items_exported(self):
        """Verify key run_tracker items are in __all__"""
        from src.shared import run_tracker
        required_exports = ['RunTracker', 'get_run_history', 'get_latest_run', 'get_active_run', 'cleanup_old_runs']
        for item in required_exports:
            assert item in run_tracker.__all__, f"run_tracker.__all__ should include '{item}'"

    def test_scraper_manager_key_items_exported(self):
        """Verify key scraper_manager items are in __all__"""
        from src.shared import scraper_manager
        required_exports = ['ScraperManager', 'get_scraper_manager']
        for item in required_exports:
            assert item in scraper_manager.__all__, f"scraper_manager.__all__ should include '{item}'"

    def test_change_detector_key_items_exported(self):
        """Verify key change_detector items are in __all__"""
        from src import change_detector
        required_exports = ['ChangeReport', 'ChangeDetector']
        for item in required_exports:
            assert item in change_detector.__all__, f"change_detector.__all__ should include '{item}'"
