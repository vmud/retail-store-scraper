"""Tests for __all__ exports in shared modules"""

import pytest
import importlib


MODULE_PATHS = [
    "src.shared.utils",
    "src.shared.proxy_client",
    "src.shared.cache",
    "src.shared.export_service",
    "src.shared.notifications",
    "src.shared.status",
    "src.shared.request_counter",
    "src.shared.session_factory",
    "src.shared.cloud_storage",
    "src.shared.run_tracker",
    "src.shared.scraper_manager",
    "src.change_detector",
]


@pytest.mark.parametrize("module_path", MODULE_PATHS)
def test_module_has_all_declaration(module_path):
    """Test that the module defines __all__ correctly.

    Args:
        module_path: Dotted path to the module to test
    """
    module = importlib.import_module(module_path)
    assert hasattr(module, '__all__'), f"{module_path} module should define __all__"
    assert isinstance(module.__all__, list), f"{module_path}.__all__ should be a list"
    assert len(module.__all__) > 0, f"{module_path}.__all__ should not be empty"


@pytest.mark.parametrize("module_path", MODULE_PATHS)
def test_exported_items_exist(module_path):
    """Test that all items in __all__ actually exist in the module.

    Args:
        module_path: Dotted path to the module to test
    """
    module = importlib.import_module(module_path)
    for item in module.__all__:
        assert hasattr(module, item), f"{module_path}.__all__ includes '{item}' but it doesn't exist"


@pytest.mark.parametrize("module_path", MODULE_PATHS)
def test_no_private_items_in_exports(module_path):
    """Test that __all__ doesn't include private (underscore-prefixed) items.

    Args:
        module_path: Dotted path to the module to test
    """
    module = importlib.import_module(module_path)
    private_items = [item for item in module.__all__ if item.startswith('_')]
    assert not private_items, f"{module_path}.__all__ should not include private items: {private_items}"


# Define key exports for each module
KEY_EXPORTS = {
    "src.shared.utils": [
        'setup_logging', 'get_headers', 'random_delay', 'select_delays',
        'get_with_retry', 'save_checkpoint', 'load_checkpoint',
        'save_to_csv', 'save_to_json', 'validate_store_data', 'validate_stores_batch',
        'ValidationResult', 'get_retailer_proxy_config', 'load_retailer_config',
        'get_proxy_client', 'get_with_proxy', 'create_proxied_session', 'ProxiedSession'
    ],
    "src.shared.proxy_client": [
        'ProxyMode', 'ProxyConfig', 'ProxyResponse', 'ProxyClient', 'create_proxy_client'
    ],
    "src.shared.cache": [
        'URLCache', 'RichURLCache'
    ],
    "src.shared.export_service": [
        'ExportFormat', 'ExportService', 'sanitize_csv_value', 'parse_format_list'
    ],
    "src.shared.notifications": [
        'NotificationProvider', 'SlackNotifier', 'ConsoleNotifier', 'NotificationManager', 'get_notifier'
    ],
    "src.shared.status": [
        'load_retailers_config', 'get_checkpoint_path', 'get_retailer_status',
        'get_all_retailers_status', 'get_progress_status'
    ],
    "src.shared.request_counter": [
        'RequestCounter', 'check_pause_logic'
    ],
    "src.shared.session_factory": [
        'create_session_factory'
    ],
    "src.shared.cloud_storage": [
        'CloudStorageProvider', 'GCSProvider', 'CloudStorageManager', 'get_cloud_storage'
    ],
    "src.shared.run_tracker": [
        'RunTracker', 'get_run_history', 'get_latest_run', 'get_active_run', 'cleanup_old_runs'
    ],
    "src.shared.scraper_manager": [
        'ScraperManager', 'get_scraper_manager'
    ],
    "src.change_detector": [
        'ChangeReport', 'ChangeDetector'
    ],
}


@pytest.mark.parametrize("module_path,required_exports", KEY_EXPORTS.items())
def test_key_public_items_are_exported(module_path, required_exports):
    """Verify key public items are included in __all__.

    Args:
        module_path: Dotted path to the module to test
        required_exports: List of items that must be exported
    """
    module = importlib.import_module(module_path)
    missing_exports = set(required_exports) - set(module.__all__)
    assert not missing_exports, f"{module_path}.__all__ is missing required exports: {missing_exports}"
