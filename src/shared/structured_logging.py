"""Structured logging and metrics for observability and control room dashboard.

This module provides a standardized logging interface that emits JSON-formatted
log events for parsing by monitoring systems, dashboards, and alerting tools.

Key features:
- JSON-structured log events for machine parsing
- Request/response tracking with latency and status codes
- Heartbeat events for stall detection
- Trace ID correlation across requests
- Phase-based event categorization (discovery, extraction, export)
- Built-in metrics aggregation (success rate, latency, error counts)

Usage:
    from src.shared.structured_logging import StructuredLogger, MetricsAggregator

    # In scraper:
    logger = StructuredLogger(retailer='verizon')

    # Track requests:
    start = time.time()
    response = session.get(url)
    logger.log_request(url, response.status_code, time.time() - start)

    # Heartbeat for progress:
    logger.log_heartbeat(stores_processed=100, phase='extraction')

    # Aggregate metrics:
    metrics = MetricsAggregator()
    metrics.add_request(status=200, latency_ms=150.5)
    summary = metrics.get_summary()
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum

__all__ = [
    'LogEvent',
    'EventType',
    'Phase',
    'StructuredLogger',
    'MetricsAggregator',
    'create_logger',
]


class EventType(str, Enum):
    """Standard event types for structured logging."""
    REQUEST_START = 'request_start'
    REQUEST_END = 'request_end'
    STORE_PROCESSED = 'store_processed'
    HEARTBEAT = 'heartbeat'
    ERROR = 'error'
    PHASE_START = 'phase_start'
    PHASE_END = 'phase_end'
    CHECKPOINT = 'checkpoint'
    RATE_LIMIT = 'rate_limit'
    RETRY = 'retry'


class Phase(str, Enum):
    """Scraping workflow phases."""
    INITIALIZATION = 'initialization'
    DISCOVERY = 'discovery'
    EXTRACTION = 'extraction'
    VALIDATION = 'validation'
    EXPORT = 'export'
    CLEANUP = 'cleanup'


@dataclass
class LogEvent:
    """Standard log event structure for observability.

    All timestamps are in ISO 8601 format (UTC).
    Trace ID allows correlation of related events across phases.

    Attributes:
        timestamp: ISO 8601 timestamp (UTC)
        trace_id: Unique ID for this scraping run (8-char UUID)
        retailer: Retailer name (verizon, target, etc)
        phase: Current workflow phase
        event: Event type (request_end, heartbeat, error, etc)
        url: Request URL (optional)
        status: HTTP status code (optional)
        latency_ms: Request latency in milliseconds (optional)
        retry_count: Number of retries attempted (optional)
        store_count: Number of stores processed (optional)
        error: Error message (optional)
        metadata: Additional context data (optional)
    """
    timestamp: str
    trace_id: str
    retailer: str
    phase: str
    event: str
    url: Optional[str] = None
    status: Optional[int] = None
    latency_ms: Optional[float] = None
    retry_count: Optional[int] = None
    store_count: Optional[int] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        """Serialize event to JSON string.

        Returns:
            JSON string representation of the event
        """
        # Filter out None values for cleaner output
        data = {k: v for k, v in asdict(self).items() if v is not None}
        return json.dumps(data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary.

        Returns:
            Dictionary representation of the event
        """
        return {k: v for k, v in asdict(self).items() if v is not None}


class StructuredLogger:
    """Emit structured log events for observability.

    This logger wraps Python's standard logging module but outputs
    structured JSON events that can be parsed by monitoring systems.

    Attributes:
        retailer: Retailer name for this logger instance
        trace_id: Unique run identifier (8-char UUID)
        logger: Underlying Python logger instance

    Example:
        logger = StructuredLogger(retailer='verizon')
        logger.log_request('https://example.com', 200, 150.5)
        logger.log_heartbeat(stores_processed=100, phase='extraction')
    """

    def __init__(
        self,
        retailer: str,
        trace_id: Optional[str] = None,
        logger_name: Optional[str] = None
    ):
        """Initialize structured logger.

        Args:
            retailer: Retailer name
            trace_id: Optional trace ID (generates one if not provided)
            logger_name: Optional logger name (defaults to 'structured')
        """
        self.retailer = retailer
        self.trace_id = trace_id or str(uuid.uuid4())[:8]
        self.logger = logging.getLogger(logger_name or 'structured')
        self._phase_start_times: Dict[str, float] = {}

    def _create_event(
        self,
        phase: str,
        event: str,
        **kwargs
    ) -> LogEvent:
        """Create a log event with common fields.

        Args:
            phase: Current phase
            event: Event type
            **kwargs: Additional event fields

        Returns:
            LogEvent instance
        """
        return LogEvent(
            timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            trace_id=self.trace_id,
            retailer=self.retailer,
            phase=phase,
            event=event,
            **kwargs
        )

    def log_request(
        self,
        url: str,
        status: int,
        latency_ms: float,
        retry_count: int = 0,
        phase: str = Phase.EXTRACTION.value
    ) -> None:
        """Log HTTP request completion.

        Args:
            url: Request URL
            status: HTTP status code
            latency_ms: Request latency in milliseconds
            retry_count: Number of retries (default: 0)
            phase: Current phase (default: extraction)
        """
        event = self._create_event(
            phase=phase,
            event=EventType.REQUEST_END.value,
            url=url,
            status=status,
            latency_ms=round(latency_ms, 2),
            retry_count=retry_count if retry_count > 0 else None
        )

        # Log at different levels based on status code
        if status == 200:
            self.logger.debug(event.to_json())
        elif status == 429:
            self.logger.warning(event.to_json())
        elif 400 <= status < 500:
            self.logger.warning(event.to_json())
        elif status >= 500:
            self.logger.error(event.to_json())
        else:
            self.logger.info(event.to_json())

    def log_heartbeat(
        self,
        stores_processed: int,
        phase: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Emit heartbeat for stall detection and progress monitoring.

        Args:
            stores_processed: Number of stores processed so far
            phase: Current phase
            metadata: Optional additional context
        """
        event = self._create_event(
            phase=phase,
            event=EventType.HEARTBEAT.value,
            store_count=stores_processed,
            metadata=metadata
        )
        self.logger.info(event.to_json())

    def log_error(
        self,
        error_message: str,
        phase: str,
        url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log error event.

        Args:
            error_message: Error description
            phase: Current phase
            url: Optional URL that caused error
            metadata: Optional additional context
        """
        event = self._create_event(
            phase=phase,
            event=EventType.ERROR.value,
            error=error_message,
            url=url,
            metadata=metadata
        )
        self.logger.error(event.to_json())

    def log_phase_start(self, phase: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log start of a workflow phase.

        Args:
            phase: Phase name
            metadata: Optional phase context
        """
        self._phase_start_times[phase] = time.time()
        event = self._create_event(
            phase=phase,
            event=EventType.PHASE_START.value,
            metadata=metadata
        )
        self.logger.info(event.to_json())

    def log_phase_end(
        self,
        phase: str,
        store_count: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log completion of a workflow phase.

        Args:
            phase: Phase name
            store_count: Number of stores processed in this phase
            metadata: Optional phase results
        """
        # Calculate phase duration if we tracked start time
        if phase in self._phase_start_times:
            duration_ms = (time.time() - self._phase_start_times[phase]) * 1000
            if metadata is None:
                metadata = {}
            metadata['duration_ms'] = round(duration_ms, 2)

        event = self._create_event(
            phase=phase,
            event=EventType.PHASE_END.value,
            store_count=store_count,
            metadata=metadata
        )
        self.logger.info(event.to_json())

    def log_retry(
        self,
        url: str,
        attempt: int,
        max_retries: int,
        reason: str,
        phase: str = Phase.EXTRACTION.value
    ) -> None:
        """Log retry attempt.

        Args:
            url: URL being retried
            attempt: Current attempt number (1-indexed)
            max_retries: Maximum retry attempts
            reason: Reason for retry (e.g., "429 rate limit", "connection timeout")
            phase: Current phase
        """
        event = self._create_event(
            phase=phase,
            event=EventType.RETRY.value,
            url=url,
            retry_count=attempt,
            metadata={'max_retries': max_retries, 'reason': reason}
        )
        self.logger.warning(event.to_json())

    def log_rate_limit(
        self,
        url: str,
        wait_time: float,
        phase: str = Phase.EXTRACTION.value
    ) -> None:
        """Log rate limit event.

        Args:
            url: URL that triggered rate limit
            wait_time: Wait time in seconds
            phase: Current phase
        """
        event = self._create_event(
            phase=phase,
            event=EventType.RATE_LIMIT.value,
            url=url,
            metadata={'wait_time_seconds': wait_time}
        )
        self.logger.warning(event.to_json())

    def log_checkpoint(
        self,
        checkpoint_type: str,
        phase: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log checkpoint save/load event.

        Args:
            checkpoint_type: Type of checkpoint ('save' or 'load')
            phase: Current phase
            metadata: Optional checkpoint details
        """
        if metadata is None:
            metadata = {}
        metadata['checkpoint_type'] = checkpoint_type

        event = self._create_event(
            phase=phase,
            event=EventType.CHECKPOINT.value,
            metadata=metadata
        )
        self.logger.info(event.to_json())


@dataclass
class MetricsAggregator:
    """Aggregate metrics for monitoring and alerting.

    Tracks request counts, success rates, latency statistics,
    and error distributions.

    Attributes:
        total_requests: Total number of requests
        success_count: Number of successful (2xx) requests
        client_errors: Number of 4xx errors
        server_errors: Number of 5xx errors
        rate_limits: Number of 429 rate limit errors
        latencies: List of request latencies in milliseconds
        retry_counts: List of retry counts per request

    Example:
        metrics = MetricsAggregator()
        metrics.add_request(status=200, latency_ms=150.5)
        metrics.add_request(status=429, latency_ms=300.0, retries=2)
        summary = metrics.get_summary()
        print(f"Success rate: {summary['success_rate_pct']}%")
    """

    total_requests: int = 0
    success_count: int = 0
    client_errors: int = 0  # 4xx
    server_errors: int = 0  # 5xx
    rate_limits: int = 0    # 429 specifically
    latencies: List[float] = field(default_factory=list)
    retry_counts: List[int] = field(default_factory=list)

    def add_request(
        self,
        status: int,
        latency_ms: float,
        retries: int = 0
    ) -> None:
        """Record a request.

        Args:
            status: HTTP status code
            latency_ms: Request latency in milliseconds
            retries: Number of retries (default: 0)
        """
        self.total_requests += 1
        self.latencies.append(latency_ms)

        if retries > 0:
            self.retry_counts.append(retries)

        if 200 <= status < 300:
            self.success_count += 1
        elif status == 429:
            self.rate_limits += 1
            self.client_errors += 1
        elif 400 <= status < 500:
            self.client_errors += 1
        elif status >= 500:
            self.server_errors += 1

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary.

        Returns:
            Dictionary with aggregated metrics including:
            - total_requests
            - success_rate_pct
            - avg_latency_ms
            - p95_latency_ms
            - error counts
            - retry statistics
        """
        if not self.latencies:
            return {
                'total_requests': 0,
                'success_rate_pct': 0.0,
                'avg_latency_ms': 0.0,
                'p95_latency_ms': 0.0,
                'client_errors': 0,
                'server_errors': 0,
                'rate_limits': 0,
                'total_retries': 0,
                'avg_retries': 0.0,
            }

        # Sort latencies for percentile calculation
        sorted_latencies = sorted(self.latencies)
        p95_index = int(len(sorted_latencies) * 0.95)

        return {
            'total_requests': self.total_requests,
            'success_rate_pct': round(
                (self.success_count / self.total_requests * 100) if self.total_requests > 0 else 0.0,
                2
            ),
            'avg_latency_ms': round(sum(self.latencies) / len(self.latencies), 2),
            'p95_latency_ms': round(sorted_latencies[p95_index], 2) if sorted_latencies else 0.0,
            'client_errors': self.client_errors,
            'server_errors': self.server_errors,
            'rate_limits': self.rate_limits,
            'total_retries': sum(self.retry_counts),
            'avg_retries': round(
                sum(self.retry_counts) / len(self.retry_counts) if self.retry_counts else 0.0,
                2
            ),
        }

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.total_requests = 0
        self.success_count = 0
        self.client_errors = 0
        self.server_errors = 0
        self.rate_limits = 0
        self.latencies.clear()
        self.retry_counts.clear()


def create_logger(retailer: str, trace_id: Optional[str] = None) -> StructuredLogger:
    """Factory function to create a structured logger.

    Args:
        retailer: Retailer name
        trace_id: Optional trace ID

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(retailer=retailer, trace_id=trace_id)
