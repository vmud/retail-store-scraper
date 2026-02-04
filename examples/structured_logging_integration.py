"""Example integration of structured logging with scrapers.

This module demonstrates how to integrate structured logging into
existing scraper code for observability and metrics tracking.

Run this example:
    python examples/structured_logging_integration.py
"""

import sys
import time
from pathlib import Path
from typing import Optional
import requests

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.shared.structured_logging import (
    StructuredLogger,
    MetricsAggregator,
    Phase,
)
from src.shared.utils import get_with_retry, setup_logging


def scraper_with_structured_logging(
    session: requests.Session,
    urls: list[str],
    retailer: str = 'example',
) -> dict:
    """Example scraper demonstrating structured logging integration.

    Args:
        session: requests.Session to use
        urls: List of URLs to scrape
        retailer: Retailer name

    Returns:
        Dictionary with scraping results and metrics
    """
    # Initialize structured logger and metrics
    logger = StructuredLogger(retailer=retailer)
    metrics = MetricsAggregator()

    # Log scraper start
    logger.log_phase_start(Phase.DISCOVERY.value)

    stores = []
    for i, url in enumerate(urls):
        # Track request timing
        start_time = time.time()

        # Make request with retry
        response = get_with_retry(session, url)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        if response:
            # Log successful request
            logger.log_request(
                url=url,
                status=response.status_code,
                latency_ms=latency_ms,
                phase=Phase.EXTRACTION.value,
            )

            # Track metrics
            metrics.add_request(
                status=response.status_code,
                latency_ms=latency_ms,
            )

            # Process response
            stores.append({'url': url, 'status': 'success'})

            # Emit heartbeat every 50 stores
            if (i + 1) % 50 == 0:
                logger.log_heartbeat(
                    stores_processed=len(stores),
                    phase=Phase.EXTRACTION.value,
                )
        else:
            # Log failed request
            logger.log_error(
                error_message='Request failed after retries',
                phase=Phase.EXTRACTION.value,
                url=url,
            )

    # Log phase completion with metrics
    logger.log_phase_end(
        phase=Phase.EXTRACTION.value,
        store_count=len(stores),
        metadata=metrics.get_summary(),
    )

    return {
        'stores': stores,
        'count': len(stores),
        'metrics': metrics.get_summary(),
        'trace_id': logger.trace_id,
    }


def wrapper_for_get_with_retry(
    session: requests.Session,
    url: str,
    logger: Optional[StructuredLogger] = None,
    metrics: Optional[MetricsAggregator] = None,
    **kwargs
) -> Optional[requests.Response]:
    """Wrapper around get_with_retry with structured logging.

    This function shows how to add structured logging to existing
    get_with_retry calls without modifying the core function.

    Args:
        session: requests.Session to use
        url: URL to fetch
        logger: Optional structured logger
        metrics: Optional metrics aggregator
        **kwargs: Additional arguments for get_with_retry

    Returns:
        Response object or None if failed
    """
    start_time = time.time()
    response = get_with_retry(session, url, **kwargs)
    latency_ms = (time.time() - start_time) * 1000

    if response and logger:
        logger.log_request(
            url=url,
            status=response.status_code,
            latency_ms=latency_ms,
        )

    if response and metrics:
        metrics.add_request(
            status=response.status_code,
            latency_ms=latency_ms,
        )

    return response


def example_with_error_handling():
    """Example showing error handling with structured logging."""
    setup_logging()

    logger = StructuredLogger(retailer='demo')
    metrics = MetricsAggregator()

    # Simulate various request outcomes
    test_cases = [
        ('https://example.com/success', 200, 150.0),
        ('https://example.com/rate-limit', 429, 300.0),
        ('https://example.com/server-error', 500, 1000.0),
        ('https://example.com/not-found', 404, 50.0),
    ]

    logger.log_phase_start(Phase.EXTRACTION.value)

    for url, status, latency_ms in test_cases:
        # Log the request
        logger.log_request(
            url=url,
            status=status,
            latency_ms=latency_ms,
        )

        # Track metrics
        metrics.add_request(
            status=status,
            latency_ms=latency_ms,
        )

        # Log rate limit
        if status == 429:
            logger.log_rate_limit(
                url=url,
                wait_time=30.0,
            )

        # Log error
        if status >= 500:
            logger.log_error(
                error_message=f'Server error {status}',
                phase=Phase.EXTRACTION.value,
                url=url,
            )

    logger.log_phase_end(
        phase=Phase.EXTRACTION.value,
        store_count=1,  # Only 1 success
        metadata=metrics.get_summary(),
    )

    # Print summary
    summary = metrics.get_summary()
    print(f"\nMetrics Summary:")
    print(f"  Total requests: {summary['total_requests']}")
    print(f"  Success rate: {summary['success_rate_pct']}%")
    print(f"  Avg latency: {summary['avg_latency_ms']}ms")
    print(f"  P95 latency: {summary['p95_latency_ms']}ms")
    print(f"  Rate limits: {summary['rate_limits']}")
    print(f"  Client errors: {summary['client_errors']}")
    print(f"  Server errors: {summary['server_errors']}")


if __name__ == '__main__':
    print("Structured Logging Integration Example\n")
    example_with_error_handling()
    print("\nCheck logs for JSON-structured events!")
