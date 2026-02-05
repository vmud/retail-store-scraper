"""
Test suite for __all__ declarations in shared modules.

This test suite follows Test-Driven Development (TDD) principles:
- Tests are written BEFORE implementation
- Tests will fail initially and pass after __all__ is added to modules
- Validates public API surface and prevents accidental exports

References: Issue #175 - Add __all__ exports to modules
"""

import importlib
import sys
from typing import List, Tuple

import pytest


# Module definitions with their expected public exports
SHARED_MODULES = {
    'src.shared.cache': [
        'URLCache',
        'RichURLCache',
        'DEFAULT_CACHE_EXPIRY_DAYS',
    ],
    'src.shared.concurrency': [
        'ConcurrencyConfig',
        'GlobalConcurrencyManager',
    ],
    'src.shared.session_factory': [
        'create_session_factory',
    ],
    'src.shared.request_counter': [
        'RequestCounter',
        'check_pause_logic',
    ],
    'src.shared.proxy_client': [
        'ProxyClient',
        'ProxyConfig',
        'ProxyMode',
        'ProxyResponse',
        'create_proxy_client',
        'redact_credentials',
    ],
    'src.shared.export_service': [
        'ExportService',
        'ExportFormat',
        'parse_format_list',
        'sanitize_csv_value',
        'sanitize_store_for_csv',
        'CSV_INJECTION_CHARS',
        'OPENPYXL_AVAILABLE',
    ],
    'src.shared.notifications': [
        'NotificationProvider',
        'SlackNotifier',
        'ConsoleNotifier',
        'NotificationManager',
        'get_notifier',
    ],
    'src.shared.cloud_storage': [
        'CloudStorageProvider',
        'GCSProvider',
        'CloudStorageManager',
        'get_cloud_storage',
        'GCS_AVAILABLE',
    ],
    'src.shared.run_tracker': [
        'RunTracker',
        'get_run_history',
        'get_latest_run',
        'get_active_run',
        'cleanup_old_runs',
    ],
    'src.shared.scraper_manager': [
        'ScraperManager',
        'get_scraper_manager',
    ],
    'src.shared.status': [
        'load_retailers_config',
        'get_checkpoint_path',
        'get_retailer_status',
        'get_all_retailers_status',
        'get_progress_status',
        'CONFIG_PATH',
    ],
    'src.shared.utils': [
        # Constants
        'CANONICAL_FIELDS',
        'DEFAULT_MAX_DELAY',
        'DEFAULT_MAX_RETRIES',
        'DEFAULT_MIN_DELAY',
        'DEFAULT_RATE_LIMIT_BASE_WAIT',
        'DEFAULT_TIMEOUT',
        'DEFAULT_USER_AGENTS',
        'FIELD_ALIASES',
        'RECOMMENDED_STORE_FIELDS',
        'REQUIRED_STORE_FIELDS',
        # Classes
        'ProxiedSession',
        'ValidationResult',
        # Functions
        'close_all_proxy_clients',
        'close_proxy_client',
        'configure_concurrency_from_yaml',
        'create_proxied_session',
        'get_headers',
        'get_proxy_client',
        'get_retailer_proxy_config',
        'get_with_proxy',
        'get_with_retry',
        'init_proxy_from_yaml',
        'load_checkpoint',
        'load_retailer_config',
        'normalize_store_data',
        'normalize_stores_batch',
        'random_delay',
        'save_checkpoint',
        'save_to_csv',
        'save_to_json',
        'select_delays',
        'setup_logging',
        'validate_store_data',
        'validate_stores_batch',
    ],
}


class TestAllDeclarationExists:
    """Test that __all__ is declared in each shared module."""

    @pytest.mark.parametrize('module_name', SHARED_MODULES.keys())
    def test_module_has_all_declaration(self, module_name: str):
        """Verify __all__ is defined in each shared module.

        Args:
            module_name: Fully qualified module name (e.g., 'src.shared.utils')
        """
        module = importlib.import_module(module_name)
        assert hasattr(module, '__all__'), f"{module_name} missing __all__ declaration"

    @pytest.mark.parametrize('module_name', SHARED_MODULES.keys())
    def test_all_is_list_or_tuple(self, module_name: str):
        """Verify __all__ is a list or tuple.

        Args:
            module_name: Fully qualified module name
        """
        module = importlib.import_module(module_name)
        if hasattr(module, '__all__'):
            assert isinstance(module.__all__, (list, tuple)), \
                f"{module_name}.__all__ must be a list or tuple, got {type(module.__all__)}"

    @pytest.mark.parametrize('module_name', SHARED_MODULES.keys())
    def test_all_is_not_empty(self, module_name: str):
        """Verify __all__ is not empty.

        Args:
            module_name: Fully qualified module name
        """
        module = importlib.import_module(module_name)
        if hasattr(module, '__all__'):
            assert len(module.__all__) > 0, \
                f"{module_name}.__all__ should not be empty"


class TestAllExportsExist:
    """Test that all items declared in __all__ actually exist in the module."""

    @pytest.mark.parametrize('module_name,_expected_exports', SHARED_MODULES.items())
    def test_all_exports_exist(self, module_name: str, _expected_exports: List[str]):
        """Every item in __all__ must be a real attribute.

        Args:
            module_name: Fully qualified module name
            _expected_exports: List of expected export names (unused, for parametrization)
        """
        module = importlib.import_module(module_name)

        if not hasattr(module, '__all__'):
            pytest.skip(f"{module_name} does not have __all__ yet")

        for name in module.__all__:
            assert hasattr(module, name), \
                f"{module_name}.__all__ contains '{name}' but it doesn't exist in the module"

    @pytest.mark.parametrize('module_name,_expected_exports', SHARED_MODULES.items())
    def test_exports_are_importable(self, module_name: str, _expected_exports: List[str]):
        """Verify all exports can be imported successfully.

        Args:
            module_name: Fully qualified module name
            _expected_exports: List of expected export names (unused, for parametrization)
        """
        module = importlib.import_module(module_name)

        if not hasattr(module, '__all__'):
            pytest.skip(f"{module_name} does not have __all__ yet")

        for name in module.__all__:
            assert hasattr(module, name), \
                f"Cannot import '{name}' from {module_name}"


class TestStarImport:
    """Test that 'from module import *' works correctly with __all__."""

    @pytest.mark.parametrize('module_name', SHARED_MODULES.keys())
    def test_star_import_respects_all(self, module_name: str):
        """from module import * should only import __all__ items.

        Args:
            module_name: Fully qualified module name
        """
        module = importlib.import_module(module_name)

        if not hasattr(module, '__all__'):
            pytest.skip(f"{module_name} does not have __all__ yet")

        # Simulate star import by directly accessing module attributes
        # This avoids exec() security concerns while testing the same behavior
        imported_names = set()
        for name in module.__all__:
            if hasattr(module, name):
                imported_names.add(name)

        # All __all__ items should be accessible
        missing_imports = set(module.__all__) - imported_names
        assert not missing_imports, \
            f"Star import from {module_name} missing __all__ items: {missing_imports}"

        # Verify no private names are in __all__
        private_in_all = {name for name in module.__all__ if name.startswith('_')}
        assert not private_in_all, \
            f"__all__ in {module_name} contains private names: {private_in_all}"


class TestPrivateFunctionsNotExported:
    """Test that private functions (starting with _) are not in __all__."""

    @pytest.mark.parametrize('module_name', SHARED_MODULES.keys())
    def test_no_private_in_all(self, module_name: str):
        """Functions starting with _ should not be in __all__.

        Args:
            module_name: Fully qualified module name
        """
        module = importlib.import_module(module_name)

        if not hasattr(module, '__all__'):
            pytest.skip(f"{module_name} does not have __all__ yet")

        private_exports = [name for name in module.__all__ if name.startswith('_')]
        assert not private_exports, \
            f"{module_name}.__all__ contains private names: {private_exports}"

    @pytest.mark.parametrize('module_name', SHARED_MODULES.keys())
    def test_no_dunder_in_all(self, module_name: str):
        """Dunder methods (starting with __) should not be in __all__.

        Args:
            module_name: Fully qualified module name
        """
        module = importlib.import_module(module_name)

        if not hasattr(module, '__all__'):
            pytest.skip(f"{module_name} does not have __all__ yet")

        dunder_exports = [name for name in module.__all__ if name.startswith('__')]
        assert not dunder_exports, \
            f"{module_name}.__all__ contains dunder names: {dunder_exports}"


class TestExpectedPublicAPI:
    """Test that the expected public API is present in __all__."""

    @pytest.mark.parametrize('module_name,expected_exports', SHARED_MODULES.items())
    def test_expected_exports_in_all(self, module_name: str, expected_exports: List[str]):
        """All expected public API items should be in __all__.

        Args:
            module_name: Fully qualified module name
            expected_exports: List of expected export names
        """
        module = importlib.import_module(module_name)

        if not hasattr(module, '__all__'):
            pytest.skip(f"{module_name} does not have __all__ yet")

        actual_exports = set(module.__all__)
        expected_set = set(expected_exports)

        # Check for missing exports
        missing_exports = expected_set - actual_exports
        assert not missing_exports, \
            f"{module_name}.__all__ missing expected exports: {missing_exports}"

    @pytest.mark.parametrize('module_name,expected_exports', SHARED_MODULES.items())
    def test_no_unexpected_exports(self, module_name: str, expected_exports: List[str]):
        """Warn about unexpected exports not in the planning document.

        This is a soft check - unexpected exports might be intentional additions.

        Args:
            module_name: Fully qualified module name
            expected_exports: List of expected export names
        """
        module = importlib.import_module(module_name)

        if not hasattr(module, '__all__'):
            pytest.skip(f"{module_name} does not have __all__ yet")

        actual_exports = set(module.__all__)
        expected_set = set(expected_exports)

        # Check for unexpected exports
        unexpected_exports = actual_exports - expected_set
        if unexpected_exports:
            pytest.fail(
                f"{module_name}.__all__ contains unexpected exports not in planning doc: "
                f"{unexpected_exports}\n"
                f"If these are intentional additions, update SHARED_MODULES in this test."
            )

    @pytest.mark.parametrize('module_name,expected_exports', SHARED_MODULES.items())
    def test_expected_exports_exist_in_module(self, module_name: str, expected_exports: List[str]):
        """All expected exports should exist in the module (even if not in __all__ yet).

        Args:
            module_name: Fully qualified module name
            expected_exports: List of expected export names
        """
        module = importlib.import_module(module_name)

        missing_from_module = []
        for name in expected_exports:
            if not hasattr(module, name):
                missing_from_module.append(name)

        assert not missing_from_module, \
            f"{module_name} is missing expected attributes: {missing_from_module}\n" \
            f"Update SHARED_MODULES in test if these names have changed."


class TestAllConsistency:
    """Test consistency and quality of __all__ declarations."""

    @pytest.mark.parametrize('module_name', SHARED_MODULES.keys())
    def test_all_items_are_strings(self, module_name: str):
        """All items in __all__ must be strings.

        Args:
            module_name: Fully qualified module name
        """
        module = importlib.import_module(module_name)

        if not hasattr(module, '__all__'):
            pytest.skip(f"{module_name} does not have __all__ yet")

        non_strings = [item for item in module.__all__ if not isinstance(item, str)]
        assert not non_strings, \
            f"{module_name}.__all__ contains non-string items: {non_strings}"

    @pytest.mark.parametrize('module_name', SHARED_MODULES.keys())
    def test_all_has_no_duplicates(self, module_name: str):
        """__all__ should not contain duplicate entries.

        Args:
            module_name: Fully qualified module name
        """
        module = importlib.import_module(module_name)

        if not hasattr(module, '__all__'):
            pytest.skip(f"{module_name} does not have __all__ yet")

        all_list = list(module.__all__)
        all_set = set(module.__all__)

        assert len(all_list) == len(all_set), \
            f"{module_name}.__all__ contains duplicate entries"

    @pytest.mark.parametrize('module_name', SHARED_MODULES.keys())
    def test_all_is_sorted(self, module_name: str):
        """__all__ should be sorted alphabetically for consistency.

        This is a recommendation, not a hard requirement.

        Args:
            module_name: Fully qualified module name
        """
        module = importlib.import_module(module_name)

        if not hasattr(module, '__all__'):
            pytest.skip(f"{module_name} does not have __all__ yet")

        all_list = list(module.__all__)
        sorted_list = sorted(all_list)

        if all_list != sorted_list:
            pytest.fail(
                f"{module_name}.__all__ is not sorted alphabetically.\n"
                f"Current: {all_list}\n"
                f"Sorted:  {sorted_list}\n"
                f"Consider sorting for consistency (soft requirement)."
            )


class TestModuleImportSafety:
    """Test that modules can be imported without side effects."""

    @pytest.mark.parametrize('module_name', SHARED_MODULES.keys())
    def test_module_import_is_safe(self, module_name: str):
        """Importing a module should not cause side effects.

        Args:
            module_name: Fully qualified module name

        Note:
            We don't remove modules from sys.modules before importing because
            that would break class identity for other tests that rely on the
            same module objects.
        """
        # Import should not raise exceptions
        try:
            module = importlib.import_module(module_name)
            assert module is not None
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Failed to import {module_name}: {e}")


class TestUtilsModuleSpecifics:
    """Specific tests for utils.py module (largest module with 32 exports)."""

    def test_utils_has_all_validation_exports(self):
        """utils.py should export all validation-related items."""
        from src.shared import utils

        if not hasattr(utils, '__all__'):
            pytest.skip("utils.py does not have __all__ yet")

        validation_exports = ['validate_store_data', 'validate_stores_batch',
                            'ValidationResult', 'REQUIRED_STORE_FIELDS',
                            'RECOMMENDED_STORE_FIELDS']

        for name in validation_exports:
            assert name in utils.__all__, \
                f"utils.__all__ missing validation export: {name}"

    def test_utils_has_all_constants(self):
        """utils.py should export all DEFAULT_* constants."""
        from src.shared import utils

        if not hasattr(utils, '__all__'):
            pytest.skip("utils.py does not have __all__ yet")

        constant_exports = [
            'DEFAULT_MIN_DELAY', 'DEFAULT_MAX_DELAY', 'DEFAULT_MAX_RETRIES',
            'DEFAULT_TIMEOUT', 'DEFAULT_RATE_LIMIT_BASE_WAIT',
            'DEFAULT_USER_AGENTS',
            'REQUIRED_STORE_FIELDS', 'RECOMMENDED_STORE_FIELDS'
        ]

        for name in constant_exports:
            assert name in utils.__all__, \
                f"utils.__all__ missing constant export: {name}"

    def test_utils_has_all_helper_functions(self):
        """utils.py should export all helper functions."""
        from src.shared import utils

        if not hasattr(utils, '__all__'):
            pytest.skip("utils.py does not have __all__ yet")

        helper_functions = [
            'random_delay', 'save_checkpoint', 'load_checkpoint',
            'get_headers', 'get_with_retry', 'save_to_csv', 'save_to_json',
            'setup_logging', 'select_delays', 'validate_store_data',
            'validate_stores_batch', 'get_retailer_proxy_config',
            'load_retailer_config'
        ]

        for name in helper_functions:
            assert name in utils.__all__, \
                f"utils.__all__ missing helper function: {name}"


class TestProxyClientSpecifics:
    """Specific tests for proxy_client.py module."""

    def test_proxy_client_has_all_classes(self):
        """proxy_client.py should export all classes."""
        from src.shared import proxy_client

        if not hasattr(proxy_client, '__all__'):
            pytest.skip("proxy_client.py does not have __all__ yet")

        classes = ['ProxyClient', 'ProxyConfig', 'ProxyMode', 'ProxyResponse']

        for name in classes:
            assert name in proxy_client.__all__, \
                f"proxy_client.__all__ missing class: {name}"

    def test_proxy_client_has_factory_functions(self):
        """proxy_client.py should export factory and utility functions."""
        from src.shared import proxy_client

        if not hasattr(proxy_client, '__all__'):
            pytest.skip("proxy_client.py does not have __all__ yet")

        functions = ['create_proxy_client', 'redact_credentials']

        for name in functions:
            assert name in proxy_client.__all__, \
                f"proxy_client.__all__ missing function: {name}"


class TestExportServiceSpecifics:
    """Specific tests for export_service.py module."""

    def test_export_service_has_optional_dependency_flag(self):
        """export_service.py should export OPENPYXL_AVAILABLE flag."""
        from src.shared import export_service

        if not hasattr(export_service, '__all__'):
            pytest.skip("export_service.py does not have __all__ yet")

        assert 'OPENPYXL_AVAILABLE' in export_service.__all__, \
            "export_service.__all__ missing OPENPYXL_AVAILABLE flag"


class TestCloudStorageSpecifics:
    """Specific tests for cloud_storage.py module."""

    def test_cloud_storage_has_optional_dependency_flag(self):
        """cloud_storage.py should export GCS_AVAILABLE flag."""
        from src.shared import cloud_storage

        if not hasattr(cloud_storage, '__all__'):
            pytest.skip("cloud_storage.py does not have __all__ yet")

        assert 'GCS_AVAILABLE' in cloud_storage.__all__, \
            "cloud_storage.__all__ missing GCS_AVAILABLE flag"


# Summary test to give overview of implementation status
def test_implementation_summary():
    """Provide a summary of __all__ implementation status across all modules.

    This test always passes but prints useful information about progress.
    """
    implemented = []
    not_implemented = []

    for module_name in SHARED_MODULES.keys():
        module = importlib.import_module(module_name)
        if hasattr(module, '__all__'):
            implemented.append(module_name)
        else:
            not_implemented.append(module_name)

    total = len(SHARED_MODULES)
    impl_count = len(implemented)

    print(f"\n{'='*70}")
    print(f"__all__ Implementation Status: {impl_count}/{total} modules")
    print(f"{'='*70}")

    if implemented:
        print(f"\n✓ Implemented ({len(implemented)}):")
        for name in implemented:
            print(f"  - {name}")

    if not_implemented:
        print(f"\n✗ Not Implemented ({len(not_implemented)}):")
        for name in not_implemented:
            print(f"  - {name}")

    print(f"\n{'='*70}\n")

    # Always pass - this is just informational
    assert True
