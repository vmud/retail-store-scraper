"""Unit tests for shared ScrapeRunner orchestration framework."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.shared.scrape_runner import ScrapeRunner, ScraperContext


class TestScraperContext:
    """Tests for ScraperContext dataclass."""

    def test_scraper_context_minimal(self):
        """Test creating context with required fields only."""
        context = ScraperContext(
            retailer='test',
            session=Mock(),
            config={}
        )

        assert context.retailer == 'test'
        assert context.resume is False
        assert context.limit is None
        assert context.refresh_urls is False
        assert context.use_rich_cache is False

    def test_scraper_context_full(self):
        """Test creating context with all fields."""
        session = Mock()
        config = {'proxy': {'mode': 'residential'}}

        context = ScraperContext(
            retailer='att',
            session=session,
            config=config,
            resume=True,
            limit=100,
            refresh_urls=True,
            use_rich_cache=True
        )

        assert context.retailer == 'att'
        assert context.session == session
        assert context.config == config
        assert context.resume is True
        assert context.limit == 100
        assert context.refresh_urls is True
        assert context.use_rich_cache is True


class TestScrapeRunnerInit:
    """Tests for ScrapeRunner initialization."""

    def test_init_with_minimal_context(self):
        """Test runner initialization with minimal context."""
        context = ScraperContext(
            retailer='test',
            session=Mock(),
            config={}
        )

        runner = ScrapeRunner(context)

        assert runner.retailer == 'test'
        assert runner.proxy_mode == 'direct'
        assert runner.parallel_workers == 1  # Default for direct mode
        assert len(runner.stores) == 0
        assert len(runner.completed_items) == 0
        assert runner.checkpoints_used is False

    def test_init_with_proxy_mode(self):
        """Test runner initialization with proxy configuration."""
        context = ScraperContext(
            retailer='test',
            session=Mock(),
            config={
                'proxy': {'mode': 'residential'},
                'parallel_workers': 10
            }
        )

        runner = ScrapeRunner(context)

        assert runner.proxy_mode == 'residential'
        assert runner.parallel_workers == 10

    def test_init_uses_default_workers_for_proxy(self):
        """Test runner uses higher default workers for proxy mode."""
        context = ScraperContext(
            retailer='test',
            session=Mock(),
            config={'proxy': {'mode': 'residential'}}
        )

        runner = ScrapeRunner(context)

        # Should use WORKERS.PROXIED_WORKERS (5) instead of DIRECT_WORKERS (1)
        assert runner.parallel_workers == 5


class TestScrapeRunnerCheckpoint:
    """Tests for checkpoint load/save functionality."""

    @patch('src.shared.scrape_runner.utils.load_checkpoint')
    def test_load_checkpoint_when_resume_enabled(self, mock_load):
        """Test checkpoint loading when resume is enabled."""
        mock_load.return_value = {
            'stores': [{'store_id': '1', 'name': 'Store 1'}],
            'completed_urls': ['url1', 'url2']
        }

        context = ScraperContext(
            retailer='test',
            session=Mock(),
            config={},
            resume=True
        )

        runner = ScrapeRunner(context)
        runner._load_checkpoint()

        assert len(runner.stores) == 1
        assert len(runner.completed_items) == 2
        assert runner.checkpoints_used is True
        assert 'url1' in runner.completed_items

    @patch('src.shared.scrape_runner.utils.load_checkpoint')
    def test_load_checkpoint_when_resume_disabled(self, mock_load):
        """Test checkpoint not loaded when resume is disabled."""
        context = ScraperContext(
            retailer='test',
            session=Mock(),
            config={},
            resume=False
        )

        runner = ScrapeRunner(context)
        runner._load_checkpoint()

        mock_load.assert_not_called()
        assert len(runner.stores) == 0
        assert runner.checkpoints_used is False

    @patch('src.shared.scrape_runner.utils.save_checkpoint')
    def test_save_checkpoint(self, mock_save):
        """Test checkpoint saving."""
        context = ScraperContext(
            retailer='test',
            session=Mock(),
            config={}
        )

        runner = ScrapeRunner(context)
        runner.stores = [{'store_id': '1'}]
        runner.completed_items = {'url1'}
        runner._save_checkpoint()

        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]

        assert saved_data['completed_count'] == 1
        assert 'url1' in saved_data['completed_urls']
        assert saved_data['stores'] == [{'store_id': '1'}]


class TestScrapeRunnerURLCache:
    """Tests for URL caching functionality."""

    @patch('src.shared.scrape_runner.URLCache')
    def test_load_from_cache_hit(self, mock_cache_class):
        """Test loading URLs from valid cache."""
        mock_cache = Mock()
        mock_cache.get.return_value = ['url1', 'url2', 'url3']
        mock_cache_class.return_value = mock_cache

        context = ScraperContext(
            retailer='test',
            session=Mock(),
            config={},
            refresh_urls=False
        )

        runner = ScrapeRunner(context)
        discovery_func = Mock(return_value=['url4', 'url5'])

        urls = runner._load_or_discover_urls(discovery_func)

        assert urls == ['url1', 'url2', 'url3']
        discovery_func.assert_not_called()
        mock_cache.get.assert_called_once()

    @patch('src.shared.scrape_runner.URLCache')
    def test_load_from_cache_miss(self, mock_cache_class):
        """Test discovering URLs when cache misses."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        context = ScraperContext(
            retailer='test',
            session=Mock(),
            config={},
            refresh_urls=False
        )

        runner = ScrapeRunner(context)
        discovery_func = Mock(return_value=['url1', 'url2'])

        urls = runner._load_or_discover_urls(discovery_func)

        assert urls == ['url1', 'url2']
        discovery_func.assert_called_once()
        mock_cache.set.assert_called_once_with(['url1', 'url2'])

    @patch('src.shared.scrape_runner.URLCache')
    def test_refresh_urls_ignores_cache(self, mock_cache_class):
        """Test that refresh_urls=True skips cache."""
        mock_cache = Mock()
        mock_cache.get.return_value = ['cached1', 'cached2']
        mock_cache_class.return_value = mock_cache

        context = ScraperContext(
            retailer='test',
            session=Mock(),
            config={},
            refresh_urls=True
        )

        runner = ScrapeRunner(context)
        discovery_func = Mock(return_value=['fresh1', 'fresh2'])

        urls = runner._load_or_discover_urls(discovery_func)

        assert urls == ['fresh1', 'fresh2']
        discovery_func.assert_called_once()
        mock_cache.get.assert_not_called()


class TestScrapeRunnerOrchestration:
    """Tests for full orchestration flow."""

    @patch('src.shared.scrape_runner.utils.validate_stores_batch')
    @patch('src.shared.scrape_runner.URLCache')
    def test_run_with_checkpoints_minimal(self, mock_cache_class, mock_validate):
        """Test minimal successful run."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_validate.return_value = {
            'total': 2,
            'valid': 2,
            'warning_count': 0
        }

        context = ScraperContext(
            retailer='test',
            session=Mock(),
            config={}
        )

        runner = ScrapeRunner(context)

        # Mock discovery and extraction
        discovery_func = Mock(return_value=['url1', 'url2'])
        extraction_func = Mock(side_effect=[
            {'store_id': '1', 'name': 'Store 1'},
            {'store_id': '2', 'name': 'Store 2'}
        ])

        result = runner.run_with_checkpoints(
            url_discovery_func=discovery_func,
            extraction_func=extraction_func
        )

        assert result['count'] == 2
        assert len(result['stores']) == 2
        assert result['checkpoints_used'] is False

    @patch('src.shared.scrape_runner.utils.validate_stores_batch')
    @patch('src.shared.scrape_runner.URLCache')
    def test_run_with_limit(self, mock_cache_class, mock_validate):
        """Test run respects limit parameter."""
        mock_cache = Mock()
        mock_cache.get.return_value = ['url1', 'url2', 'url3']
        mock_cache_class.return_value = mock_cache

        mock_validate.return_value = {'total': 2, 'valid': 2, 'warning_count': 0}

        context = ScraperContext(
            retailer='test',
            session=Mock(),
            config={},
            limit=2
        )

        runner = ScrapeRunner(context)
        discovery_func = Mock()
        extraction_func = Mock(return_value={'store_id': '1'})

        result = runner.run_with_checkpoints(
            url_discovery_func=discovery_func,
            extraction_func=extraction_func
        )

        # Should only process 2 items even though 3 URLs available
        assert extraction_func.call_count == 2


    @patch('src.shared.scrape_runner.utils.validate_stores_batch')
    @patch('src.shared.scrape_runner.URLCache')
    def test_run_with_empty_discovery(self, mock_cache_class, mock_validate):
        """Test run handles empty URL discovery."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        context = ScraperContext(
            retailer='test',
            session=Mock(),
            config={}
        )

        runner = ScrapeRunner(context)
        discovery_func = Mock(return_value=[])

        result = runner.run_with_checkpoints(
            url_discovery_func=discovery_func,
            extraction_func=Mock()
        )

        assert result['stores'] == []
        assert result['count'] == 0
        assert result['checkpoints_used'] is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
