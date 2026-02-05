"""Tests for structured logging and metrics aggregation."""

import json
import logging
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.shared.structured_logging import (
    LogEvent,
    EventType,
    Phase,
    StructuredLogger,
    MetricsAggregator,
    create_logger,
)


class TestLogEvent:
    """Tests for LogEvent dataclass."""

    def test_log_event_creation(self):
        """LogEvent should be created with required fields."""
        event = LogEvent(
            timestamp='2026-02-04T12:00:00Z',
            trace_id='abc123',
            retailer='verizon',
            phase='extraction',
            event='request_end',
        )

        assert event.timestamp == '2026-02-04T12:00:00Z'
        assert event.trace_id == 'abc123'
        assert event.retailer == 'verizon'
        assert event.phase == 'extraction'
        assert event.event == 'request_end'

    def test_log_event_to_json(self):
        """LogEvent.to_json() should serialize to valid JSON."""
        event = LogEvent(
            timestamp='2026-02-04T12:00:00Z',
            trace_id='abc123',
            retailer='target',
            phase='extraction',
            event='request_end',
            url='https://example.com',
            status=200,
            latency_ms=150.5,
        )

        json_str = event.to_json()
        parsed = json.loads(json_str)

        assert parsed['timestamp'] == '2026-02-04T12:00:00Z'
        assert parsed['trace_id'] == 'abc123'
        assert parsed['retailer'] == 'target'
        assert parsed['url'] == 'https://example.com'
        assert parsed['status'] == 200
        assert parsed['latency_ms'] == 150.5

    def test_log_event_to_json_filters_none_values(self):
        """LogEvent.to_json() should omit None values."""
        event = LogEvent(
            timestamp='2026-02-04T12:00:00Z',
            trace_id='abc123',
            retailer='walmart',
            phase='discovery',
            event='heartbeat',
            store_count=100,
        )

        json_str = event.to_json()
        parsed = json.loads(json_str)

        # Should have these fields
        assert 'timestamp' in parsed
        assert 'store_count' in parsed

        # Should NOT have these fields (None values)
        assert 'url' not in parsed
        assert 'status' not in parsed
        assert 'latency_ms' not in parsed
        assert 'error' not in parsed

    def test_log_event_to_dict(self):
        """LogEvent.to_dict() should return filtered dictionary."""
        event = LogEvent(
            timestamp='2026-02-04T12:00:00Z',
            trace_id='abc123',
            retailer='bestbuy',
            phase='export',
            event='phase_end',
            store_count=500,
        )

        data = event.to_dict()

        assert isinstance(data, dict)
        assert data['retailer'] == 'bestbuy'
        assert data['store_count'] == 500
        assert 'url' not in data


class TestStructuredLogger:
    """Tests for StructuredLogger class."""

    def test_logger_initialization(self):
        """StructuredLogger should initialize with retailer and trace ID."""
        logger = StructuredLogger(retailer='verizon')

        assert logger.retailer == 'verizon'
        assert len(logger.trace_id) == 8  # UUID truncated to 8 chars
        assert logger.logger is not None

    def test_logger_custom_trace_id(self):
        """StructuredLogger should accept custom trace ID."""
        logger = StructuredLogger(retailer='att', trace_id='custom-id')

        assert logger.trace_id == 'custom-id'

    def test_log_request_success(self, caplog):
        """log_request should log successful request at DEBUG level."""
        logger = StructuredLogger(retailer='target')

        with caplog.at_level(logging.DEBUG):
            logger.log_request(
                url='https://example.com/store/1',
                status=200,
                latency_ms=150.5,
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]

        # Parse the JSON log
        log_data = json.loads(record.message)

        assert log_data['retailer'] == 'target'
        assert log_data['event'] == 'request_end'
        assert log_data['url'] == 'https://example.com/store/1'
        assert log_data['status'] == 200
        assert log_data['latency_ms'] == 150.5
        assert log_data['phase'] == 'extraction'

    def test_log_request_with_retry(self, caplog):
        """log_request should include retry count when > 0."""
        logger = StructuredLogger(retailer='tmobile')

        with caplog.at_level(logging.DEBUG):
            logger.log_request(
                url='https://example.com/store/2',
                status=200,
                latency_ms=300.0,
                retry_count=2,
            )

        record = caplog.records[0]
        log_data = json.loads(record.message)

        assert log_data['retry_count'] == 2

    def test_log_request_429_logs_warning(self, caplog):
        """log_request with 429 should log at WARNING level."""
        logger = StructuredLogger(retailer='walmart')

        with caplog.at_level(logging.WARNING):
            logger.log_request(
                url='https://example.com/store/3',
                status=429,
                latency_ms=200.0,
            )

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == 'WARNING'

    def test_log_request_500_logs_error(self, caplog):
        """log_request with 5xx should log at ERROR level."""
        logger = StructuredLogger(retailer='bestbuy')

        with caplog.at_level(logging.ERROR):
            logger.log_request(
                url='https://example.com/store/4',
                status=500,
                latency_ms=1000.0,
            )

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == 'ERROR'

    def test_log_heartbeat(self, caplog):
        """log_heartbeat should emit progress event."""
        logger = StructuredLogger(retailer='cricket')

        with caplog.at_level(logging.INFO):
            logger.log_heartbeat(
                stores_processed=100,
                phase='extraction',
            )

        record = caplog.records[0]
        log_data = json.loads(record.message)

        assert log_data['event'] == 'heartbeat'
        assert log_data['store_count'] == 100
        assert log_data['phase'] == 'extraction'

    def test_log_heartbeat_with_metadata(self, caplog):
        """log_heartbeat should include metadata."""
        logger = StructuredLogger(retailer='telus')

        with caplog.at_level(logging.INFO):
            logger.log_heartbeat(
                stores_processed=250,
                phase='discovery',
                metadata={'checkpoint_saved': True},
            )

        record = caplog.records[0]
        log_data = json.loads(record.message)

        assert log_data['metadata']['checkpoint_saved'] is True

    def test_log_error(self, caplog):
        """log_error should log error event."""
        logger = StructuredLogger(retailer='bell')

        with caplog.at_level(logging.ERROR):
            logger.log_error(
                error_message='Connection timeout',
                phase='extraction',
                url='https://example.com/store/5',
            )

        record = caplog.records[0]
        log_data = json.loads(record.message)

        assert log_data['event'] == 'error'
        assert log_data['error'] == 'Connection timeout'
        assert log_data['url'] == 'https://example.com/store/5'

    def test_log_phase_start(self, caplog):
        """log_phase_start should log phase start event."""
        logger = StructuredLogger(retailer='verizon')

        with caplog.at_level(logging.INFO):
            logger.log_phase_start('discovery')

        record = caplog.records[0]
        log_data = json.loads(record.message)

        assert log_data['event'] == 'phase_start'
        assert log_data['phase'] == 'discovery'

    def test_log_phase_end(self, caplog):
        """log_phase_end should log phase completion."""
        logger = StructuredLogger(retailer='att')

        with caplog.at_level(logging.INFO):
            logger.log_phase_end(
                phase='extraction',
                store_count=500,
            )

        record = caplog.records[0]
        log_data = json.loads(record.message)

        assert log_data['event'] == 'phase_end'
        assert log_data['phase'] == 'extraction'
        assert log_data['store_count'] == 500

    @patch('src.shared.structured_logging.time.time')
    def test_log_phase_end_calculates_duration(self, mock_time, caplog):
        """log_phase_end should calculate phase duration if start was logged."""
        logger = StructuredLogger(retailer='target')
        mock_time.side_effect = [1000.0, 1000.05]  # 50ms duration

        # Start phase
        logger.log_phase_start('discovery')

        with caplog.at_level(logging.INFO):
            logger.log_phase_end('discovery')

        # Find the phase_end log (not phase_start)
        phase_end_log = [r for r in caplog.records if 'phase_end' in r.message][0]
        log_data = json.loads(phase_end_log.message)

        assert 'metadata' in log_data
        assert 'duration_ms' in log_data['metadata']
        assert log_data['metadata']['duration_ms'] == 50.0

    def test_log_retry(self, caplog):
        """log_retry should log retry attempt."""
        logger = StructuredLogger(retailer='walmart')

        with caplog.at_level(logging.WARNING):
            logger.log_retry(
                url='https://example.com/store/6',
                attempt=2,
                max_retries=3,
                reason='429 rate limit',
            )

        record = caplog.records[0]
        log_data = json.loads(record.message)

        assert log_data['event'] == 'retry'
        assert log_data['retry_count'] == 2
        assert log_data['metadata']['max_retries'] == 3
        assert log_data['metadata']['reason'] == '429 rate limit'

    def test_log_rate_limit(self, caplog):
        """log_rate_limit should log rate limit event."""
        logger = StructuredLogger(retailer='bestbuy')

        with caplog.at_level(logging.WARNING):
            logger.log_rate_limit(
                url='https://example.com/store/7',
                wait_time=30.0,
            )

        record = caplog.records[0]
        log_data = json.loads(record.message)

        assert log_data['event'] == 'rate_limit'
        assert log_data['metadata']['wait_time_seconds'] == 30.0

    def test_log_checkpoint(self, caplog):
        """log_checkpoint should log checkpoint events."""
        logger = StructuredLogger(retailer='cricket')

        with caplog.at_level(logging.INFO):
            logger.log_checkpoint(
                checkpoint_type='save',
                phase='extraction',
                metadata={'stores_saved': 100},
            )

        record = caplog.records[0]
        log_data = json.loads(record.message)

        assert log_data['event'] == 'checkpoint'
        assert log_data['metadata']['checkpoint_type'] == 'save'
        assert log_data['metadata']['stores_saved'] == 100

    def test_log_checkpoint_does_not_mutate_metadata(self, caplog):
        """log_checkpoint should not mutate the caller's metadata dict."""
        logger = StructuredLogger(retailer='cricket')
        original_metadata = {'stores_saved': 100}

        with caplog.at_level(logging.INFO):
            logger.log_checkpoint(
                checkpoint_type='save',
                phase='extraction',
                metadata=original_metadata,
            )

        # Original dict should not have 'checkpoint_type' added
        assert 'checkpoint_type' not in original_metadata
        assert original_metadata == {'stores_saved': 100}

    @patch('src.shared.structured_logging.time.time')
    def test_log_phase_end_does_not_mutate_metadata(self, mock_time, caplog):
        """log_phase_end should not mutate the caller's metadata dict."""
        logger = StructuredLogger(retailer='target')
        mock_time.side_effect = [1000.0, 1000.05]  # 50ms duration
        original_metadata = {'custom_field': 'value'}

        # Start phase
        logger.log_phase_start('discovery')

        with caplog.at_level(logging.INFO):
            logger.log_phase_end('discovery', metadata=original_metadata)

        # Original dict should not have 'duration_ms' added
        assert 'duration_ms' not in original_metadata
        assert original_metadata == {'custom_field': 'value'}

    def test_trace_id_consistency(self, caplog):
        """All logs from same logger should have same trace_id."""
        logger = StructuredLogger(retailer='telus')

        with caplog.at_level(logging.DEBUG):
            logger.log_request('https://example.com/1', 200, 100.0)
            logger.log_heartbeat(10, 'extraction')
            logger.log_request('https://example.com/2', 200, 150.0)

        # Parse all logs
        trace_ids = [json.loads(r.message)['trace_id'] for r in caplog.records]

        # All should have same trace ID
        assert len(set(trace_ids)) == 1


class TestMetricsAggregator:
    """Tests for MetricsAggregator class."""

    def test_aggregator_initialization(self):
        """MetricsAggregator should initialize with zero counts."""
        metrics = MetricsAggregator()

        assert metrics.total_requests == 0
        assert metrics.success_count == 0
        assert metrics.client_errors == 0
        assert metrics.server_errors == 0
        assert metrics.rate_limits == 0
        assert len(metrics.latencies) == 0
        assert len(metrics.retry_counts) == 0

    def test_add_request_success(self):
        """add_request should track successful requests."""
        metrics = MetricsAggregator()

        metrics.add_request(status=200, latency_ms=150.5)

        assert metrics.total_requests == 1
        assert metrics.success_count == 1
        assert len(metrics.latencies) == 1
        assert metrics.latencies[0] == 150.5

    def test_add_request_with_retry(self):
        """add_request should track retry counts."""
        metrics = MetricsAggregator()

        metrics.add_request(status=200, latency_ms=300.0, retries=2)

        assert metrics.retry_counts == [2]

    def test_add_request_429(self):
        """add_request should count 429 as rate limit and client error."""
        metrics = MetricsAggregator()

        metrics.add_request(status=429, latency_ms=200.0)

        assert metrics.rate_limits == 1
        assert metrics.client_errors == 1
        assert metrics.success_count == 0

    def test_add_request_4xx(self):
        """add_request should count 4xx as client error."""
        metrics = MetricsAggregator()

        metrics.add_request(status=404, latency_ms=50.0)
        metrics.add_request(status=403, latency_ms=75.0)

        assert metrics.client_errors == 2
        assert metrics.success_count == 0

    def test_add_request_5xx(self):
        """add_request should count 5xx as server error."""
        metrics = MetricsAggregator()

        metrics.add_request(status=500, latency_ms=1000.0)
        metrics.add_request(status=503, latency_ms=800.0)

        assert metrics.server_errors == 2
        assert metrics.success_count == 0

    def test_get_summary_empty(self):
        """get_summary should handle empty metrics."""
        metrics = MetricsAggregator()

        summary = metrics.get_summary()

        assert summary['total_requests'] == 0
        assert summary['success_rate_pct'] == 0.0
        assert summary['avg_latency_ms'] == 0.0
        assert summary['p95_latency_ms'] == 0.0

    def test_get_summary_with_data(self):
        """get_summary should calculate metrics correctly."""
        metrics = MetricsAggregator()

        # Add 100 requests: 95 success, 5 failures
        for i in range(95):
            metrics.add_request(status=200, latency_ms=100.0 + i)

        for i in range(5):
            metrics.add_request(status=500, latency_ms=1000.0)

        summary = metrics.get_summary()

        assert summary['total_requests'] == 100
        assert summary['success_rate_pct'] == 95.0
        assert summary['avg_latency_ms'] > 0
        assert summary['server_errors'] == 5

    def test_get_summary_p95_latency(self):
        """get_summary should calculate 95th percentile latency."""
        metrics = MetricsAggregator()

        # Add 100 requests with latencies 1-100ms
        for i in range(1, 101):
            metrics.add_request(status=200, latency_ms=float(i))

        summary = metrics.get_summary()

        # 95th percentile of 1-100 should be 95 (math.ceil(100 * 0.95) - 1 = 94, value at index 94 is 95)
        assert summary['p95_latency_ms'] == 95.0

    def test_get_summary_p95_small_sample(self):
        """get_summary should calculate accurate P95 for small sample sizes."""
        metrics = MetricsAggregator()

        # Add only 20 requests with latencies 1-20ms
        for i in range(1, 21):
            metrics.add_request(status=200, latency_ms=float(i))

        summary = metrics.get_summary()

        # With 20 samples: math.ceil(20 * 0.95) - 1 = 19 - 1 = 18
        # Value at index 18 in sorted list [1,2,...,20] is 19 (not 20, which would be max)
        assert summary['p95_latency_ms'] == 19.0

    def test_get_summary_retry_stats(self):
        """get_summary should calculate retry statistics."""
        metrics = MetricsAggregator()

        metrics.add_request(status=200, latency_ms=150.0, retries=1)
        metrics.add_request(status=200, latency_ms=200.0, retries=2)
        metrics.add_request(status=200, latency_ms=250.0, retries=3)

        summary = metrics.get_summary()

        assert summary['total_retries'] == 6  # 1 + 2 + 3
        assert summary['avg_retries'] == 2.0  # (1 + 2 + 3) / 3

    def test_reset(self):
        """reset should clear all metrics."""
        metrics = MetricsAggregator()

        # Add some data
        metrics.add_request(status=200, latency_ms=150.0, retries=1)
        metrics.add_request(status=429, latency_ms=200.0)

        # Reset
        metrics.reset()

        # Should be back to zero
        assert metrics.total_requests == 0
        assert metrics.success_count == 0
        assert metrics.rate_limits == 0
        assert len(metrics.latencies) == 0
        assert len(metrics.retry_counts) == 0


class TestCreateLogger:
    """Tests for create_logger factory function."""

    def test_create_logger(self):
        """create_logger should create StructuredLogger instance."""
        logger = create_logger(retailer='verizon')

        assert isinstance(logger, StructuredLogger)
        assert logger.retailer == 'verizon'

    def test_create_logger_with_trace_id(self):
        """create_logger should accept trace_id."""
        logger = create_logger(retailer='att', trace_id='custom-id')

        assert logger.trace_id == 'custom-id'


class TestEnums:
    """Tests for enum types."""

    def test_event_type_values(self):
        """EventType enum should have expected values."""
        assert EventType.REQUEST_START.value == 'request_start'
        assert EventType.REQUEST_END.value == 'request_end'
        assert EventType.HEARTBEAT.value == 'heartbeat'
        assert EventType.ERROR.value == 'error'

    def test_phase_values(self):
        """Phase enum should have expected values."""
        assert Phase.INITIALIZATION.value == 'initialization'
        assert Phase.DISCOVERY.value == 'discovery'
        assert Phase.EXTRACTION.value == 'extraction'
        assert Phase.VALIDATION.value == 'validation'
        assert Phase.EXPORT.value == 'export'
