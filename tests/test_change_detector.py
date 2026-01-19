"""Unit tests for the change detection system"""

import json
import os
import shutil
import tempfile
import pytest
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.change_detector import ChangeDetector, ChangeReport


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup after tests
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_stores():
    """Sample store data for testing"""
    return [
        {
            'store_id': '1001',
            'name': 'Store One',
            'url': 'https://example.com/store/1001',
            'street_address': '123 Main St',
            'city': 'New York',
            'state': 'NY',
            'zip': '10001',
            'country': 'US',
            'latitude': '40.7128',
            'longitude': '-74.0060',
            'phone': '555-0001',
            'scraped_at': '2024-01-15T12:00:00'
        },
        {
            'store_id': '1002',
            'name': 'Store Two',
            'url': 'https://example.com/store/1002',
            'street_address': '456 Oak Ave',
            'city': 'Los Angeles',
            'state': 'CA',
            'zip': '90001',
            'country': 'US',
            'latitude': '34.0522',
            'longitude': '-118.2437',
            'phone': '555-0002',
            'scraped_at': '2024-01-15T12:00:00'
        },
        {
            'store_id': '1003',
            'name': 'Store Three',
            'url': 'https://example.com/store/1003',
            'street_address': '789 Pine Rd',
            'city': 'Chicago',
            'state': 'IL',
            'zip': '60601',
            'country': 'US',
            'latitude': '41.8781',
            'longitude': '-87.6298',
            'phone': '555-0003',
            'scraped_at': '2024-01-15T12:00:00'
        }
    ]


class TestStoreKeyGeneration:
    """Test store key generation logic"""

    def test_key_with_store_id(self, temp_data_dir):
        """Store key should use store_id when available"""
        detector = ChangeDetector('verizon', temp_data_dir)
        store = {'store_id': '1001', 'url': 'https://example.com/store'}
        key = detector._get_store_key(store)
        assert key == 'id:1001'

    def test_key_with_url_only(self, temp_data_dir):
        """Store key should use URL when no store_id"""
        detector = ChangeDetector('verizon', temp_data_dir)
        store = {'url': 'https://example.com/store', 'name': 'Test Store'}
        key = detector._get_store_key(store)
        assert key == 'url:https://example.com/store'

    def test_key_with_address_fallback(self, temp_data_dir):
        """Store key should fall back to address-based key"""
        detector = ChangeDetector('verizon', temp_data_dir)
        store = {
            'name': 'Test Store',
            'street_address': '123 Main St',
            'city': 'New York',
            'state': 'NY'
        }
        key = detector._get_store_key(store)
        assert key.startswith('addr:')
        assert 'test store' in key.lower()
        assert '123 main st' in key.lower()

    def test_bestbuy_prefers_url(self, temp_data_dir):
        """BestBuy should prefer URL over store_id (multi-service locations)"""
        detector = ChangeDetector('bestbuy', temp_data_dir)
        store = {
            'store_id': '1001',
            'url': 'https://bestbuy.com/store/1001/geeksquad'
        }
        key = detector._get_store_key(store)
        assert key.startswith('url:')

    def test_other_retailers_prefer_store_id(self, temp_data_dir):
        """Non-BestBuy retailers should prefer store_id"""
        for retailer in ['verizon', 'att', 'target', 'walmart', 'tmobile']:
            detector = ChangeDetector(retailer, temp_data_dir)
            store = {
                'store_id': '1001',
                'url': 'https://example.com/store/1001'
            }
            key = detector._get_store_key(store)
            assert key == 'id:1001', f"Failed for {retailer}"


class TestFingerprintComputation:
    """Test fingerprint hash computation"""

    def test_same_store_same_fingerprint(self, temp_data_dir):
        """Same store data should produce same fingerprint"""
        detector = ChangeDetector('verizon', temp_data_dir)
        store = {'store_id': '1001', 'city': 'New York', 'state': 'NY'}
        fp1 = detector.compute_fingerprint(store)
        fp2 = detector.compute_fingerprint(store)
        assert fp1 == fp2

    def test_different_stores_different_fingerprints(self, temp_data_dir):
        """Different store data should produce different fingerprints"""
        detector = ChangeDetector('verizon', temp_data_dir)
        store1 = {'store_id': '1001', 'city': 'New York', 'state': 'NY'}
        store2 = {'store_id': '1001', 'city': 'Los Angeles', 'state': 'CA'}
        fp1 = detector.compute_fingerprint(store1)
        fp2 = detector.compute_fingerprint(store2)
        assert fp1 != fp2

    def test_fingerprint_ignores_scraped_at(self, temp_data_dir):
        """Fingerprint should not change based on scraped_at timestamp"""
        detector = ChangeDetector('verizon', temp_data_dir)
        store1 = {'store_id': '1001', 'city': 'New York', 'scraped_at': '2024-01-01'}
        store2 = {'store_id': '1001', 'city': 'New York', 'scraped_at': '2024-01-15'}
        fp1 = detector.compute_fingerprint(store1)
        fp2 = detector.compute_fingerprint(store2)
        assert fp1 == fp2

    def test_fingerprint_is_sha256(self, temp_data_dir):
        """Fingerprint should be a valid SHA-256 hash"""
        detector = ChangeDetector('verizon', temp_data_dir)
        store = {'store_id': '1001'}
        fp = detector.compute_fingerprint(store)
        assert len(fp) == 64
        assert all(c in '0123456789abcdef' for c in fp)


class TestChangeDetection:
    """Test change detection logic"""

    def _setup_previous_data(self, detector, stores):
        """Helper to set up previous data for change detection tests.

        The change detector reads from stores_previous.json, so we need to
        directly write to that file to simulate a previous run's data.
        """
        previous_path = detector.output_dir / 'stores_previous.json'
        previous_path.parent.mkdir(parents=True, exist_ok=True)
        with open(previous_path, 'w', encoding='utf-8') as f:
            json.dump(stores, f)

    def test_first_run_all_new(self, temp_data_dir, sample_stores):
        """First run should report all stores as new"""
        detector = ChangeDetector('verizon', temp_data_dir)
        report = detector.detect_changes(sample_stores)

        assert report.retailer == 'verizon'
        assert report.total_previous == 0
        assert report.total_current == 3
        assert len(report.new_stores) == 3
        assert len(report.closed_stores) == 0
        assert len(report.modified_stores) == 0
        assert report.unchanged_count == 0

    def test_detect_new_stores(self, temp_data_dir, sample_stores):
        """Should detect newly added stores"""
        detector = ChangeDetector('verizon', temp_data_dir)

        # Set up previous data with only first 2 stores
        self._setup_previous_data(detector, sample_stores[:2])

        # Detect changes with all 3 stores
        report = detector.detect_changes(sample_stores)

        assert report.total_previous == 2
        assert report.total_current == 3
        assert len(report.new_stores) == 1
        assert report.new_stores[0]['store_id'] == '1003'

    def test_detect_closed_stores(self, temp_data_dir, sample_stores):
        """Should detect closed stores"""
        detector = ChangeDetector('verizon', temp_data_dir)

        # Set up previous data with all stores
        self._setup_previous_data(detector, sample_stores)

        # Detect changes with fewer stores (one closed)
        report = detector.detect_changes(sample_stores[:2])

        assert report.total_previous == 3
        assert report.total_current == 2
        assert len(report.closed_stores) == 1
        assert report.closed_stores[0]['store_id'] == '1003'

    def test_detect_modified_stores(self, temp_data_dir, sample_stores):
        """Should detect modified stores"""
        detector = ChangeDetector('verizon', temp_data_dir)

        # Set up previous data
        self._setup_previous_data(detector, sample_stores)

        # Modify a store
        modified_stores = [s.copy() for s in sample_stores]
        modified_stores[0] = {**sample_stores[0], 'phone': '555-9999'}

        report = detector.detect_changes(modified_stores)

        assert len(report.modified_stores) == 1
        assert report.modified_stores[0]['changes']['phone']['previous'] == '555-0001'
        assert report.modified_stores[0]['changes']['phone']['current'] == '555-9999'

    def test_no_changes(self, temp_data_dir, sample_stores):
        """Should report no changes when data is identical"""
        detector = ChangeDetector('verizon', temp_data_dir)

        # Set up previous data
        self._setup_previous_data(detector, sample_stores)

        # Detect changes with same data
        report = detector.detect_changes(sample_stores)

        assert report.has_changes is False
        assert len(report.new_stores) == 0
        assert len(report.closed_stores) == 0
        assert len(report.modified_stores) == 0
        assert report.unchanged_count == 3


class TestChangeReport:
    """Test ChangeReport class"""

    def test_has_changes_true_when_new(self):
        """has_changes should be True when there are new stores"""
        report = ChangeReport(
            retailer='test',
            timestamp='2024-01-15T12:00:00',
            previous_run=None,
            current_run='2024-01-15T12:00:00',
            total_previous=0,
            total_current=1,
            new_stores=[{'store_id': '1'}],
            closed_stores=[],
            modified_stores=[],
            unchanged_count=0
        )
        assert report.has_changes is True

    def test_has_changes_true_when_closed(self):
        """has_changes should be True when there are closed stores"""
        report = ChangeReport(
            retailer='test',
            timestamp='2024-01-15T12:00:00',
            previous_run='2024-01-14T12:00:00',
            current_run='2024-01-15T12:00:00',
            total_previous=1,
            total_current=0,
            new_stores=[],
            closed_stores=[{'store_id': '1'}],
            modified_stores=[],
            unchanged_count=0
        )
        assert report.has_changes is True

    def test_has_changes_false_when_no_changes(self):
        """has_changes should be False when there are no changes"""
        report = ChangeReport(
            retailer='test',
            timestamp='2024-01-15T12:00:00',
            previous_run='2024-01-14T12:00:00',
            current_run='2024-01-15T12:00:00',
            total_previous=5,
            total_current=5,
            new_stores=[],
            closed_stores=[],
            modified_stores=[],
            unchanged_count=5
        )
        assert report.has_changes is False

    def test_summary_format(self):
        """summary() should return formatted string"""
        report = ChangeReport(
            retailer='verizon',
            timestamp='2024-01-15T12:00:00',
            previous_run='2024-01-14T12:00:00',
            current_run='2024-01-15T12:00:00',
            total_previous=100,
            total_current=105,
            new_stores=[{}, {}, {}],
            closed_stores=[{}],
            modified_stores=[{}, {}],
            unchanged_count=99
        )
        summary = report.summary()
        assert 'verizon' in summary
        assert '+3 new' in summary
        assert '-1 closed' in summary
        assert '~2 modified' in summary
        assert '=99 unchanged' in summary

    def test_to_dict(self):
        """to_dict() should return dictionary representation"""
        report = ChangeReport(
            retailer='verizon',
            timestamp='2024-01-15T12:00:00',
            previous_run=None,
            current_run='2024-01-15T12:00:00',
            total_previous=0,
            total_current=1,
            new_stores=[{'store_id': '1'}],
            closed_stores=[],
            modified_stores=[],
            unchanged_count=0
        )
        d = report.to_dict()
        assert d['retailer'] == 'verizon'
        assert d['total_current'] == 1
        assert len(d['new_stores']) == 1


class TestFilePersistence:
    """Test file save/load operations"""

    def test_save_and_load_version(self, temp_data_dir, sample_stores):
        """Should save and load store versions correctly"""
        detector = ChangeDetector('verizon', temp_data_dir)

        # Save stores
        detector.save_version(sample_stores)

        # Verify files were created
        latest_path = Path(temp_data_dir) / 'verizon' / 'output' / 'stores_latest.json'
        assert latest_path.exists()

        # Load and verify
        with open(latest_path) as f:
            loaded = json.load(f)
        assert len(loaded) == 3
        assert loaded[0]['store_id'] == '1001'

    def test_version_rotation(self, temp_data_dir, sample_stores):
        """save_version should rotate latest to previous"""
        detector = ChangeDetector('verizon', temp_data_dir)

        # Save first version
        detector.save_version(sample_stores[:2])

        # Save second version
        detector.save_version(sample_stores)

        # Check previous file exists and has old data
        previous_path = Path(temp_data_dir) / 'verizon' / 'output' / 'stores_previous.json'
        assert previous_path.exists()

        with open(previous_path) as f:
            previous = json.load(f)
        assert len(previous) == 2

        # Check latest has new data
        latest_path = Path(temp_data_dir) / 'verizon' / 'output' / 'stores_latest.json'
        with open(latest_path) as f:
            latest = json.load(f)
        assert len(latest) == 3

    def test_save_change_report(self, temp_data_dir, sample_stores):
        """Should save change report to history directory"""
        detector = ChangeDetector('verizon', temp_data_dir)
        report = detector.detect_changes(sample_stores)

        filepath = detector.save_change_report(report)

        assert os.path.exists(filepath)
        assert 'history' in filepath
        assert 'changes_' in filepath

        with open(filepath) as f:
            saved = json.load(f)
        assert saved['retailer'] == 'verizon'
        assert len(saved['new_stores']) == 3

    def test_save_fingerprints(self, temp_data_dir, sample_stores):
        """Should save fingerprints file"""
        detector = ChangeDetector('verizon', temp_data_dir)
        detector.save_fingerprints(sample_stores)

        assert detector.fingerprints_path.exists()

        with open(detector.fingerprints_path) as f:
            data = json.load(f)

        assert 'timestamp' in data
        assert data['count'] == 3
        assert 'fingerprints' in data
        assert len(data['fingerprints']) == 3

    def test_load_nonexistent_previous(self, temp_data_dir):
        """load_previous_data should return None when no previous data"""
        detector = ChangeDetector('verizon', temp_data_dir)
        result = detector.load_previous_data()
        assert result is None


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_stores_list(self, temp_data_dir):
        """Should handle empty stores list"""
        detector = ChangeDetector('verizon', temp_data_dir)
        report = detector.detect_changes([])

        assert report.total_current == 0
        assert len(report.new_stores) == 0

    def test_store_without_id_or_url(self, temp_data_dir):
        """Should generate key from address for stores without id/url"""
        detector = ChangeDetector('verizon', temp_data_dir)
        store = {
            'name': 'Mystery Store',
            'street_address': '123 Unknown St',
            'city': 'Nowhere',
            'state': 'XX'
        }
        key = detector._get_store_key(store)
        assert key.startswith('addr:')

    def test_unicode_in_store_data(self, temp_data_dir):
        """Should handle unicode characters in store data"""
        detector = ChangeDetector('verizon', temp_data_dir)
        store = {
            'store_id': '1001',
            'name': 'Café Store \u2764',
            'city': 'São Paulo'
        }
        # Should not raise
        key = detector._get_store_key(store)
        fp = detector.compute_fingerprint(store)
        assert key is not None
        assert fp is not None

    def test_special_characters_in_store_id(self, temp_data_dir):
        """Should handle special characters in store_id"""
        detector = ChangeDetector('verizon', temp_data_dir)
        store = {'store_id': 'store-1001/main'}
        key = detector._get_store_key(store)
        assert key == 'id:store-1001/main'

    def test_directory_creation(self, temp_data_dir):
        """Should create necessary directories"""
        detector = ChangeDetector('newretailer', temp_data_dir)

        output_dir = Path(temp_data_dir) / 'newretailer' / 'output'
        history_dir = Path(temp_data_dir) / 'newretailer' / 'history'

        assert output_dir.exists()
        assert history_dir.exists()
