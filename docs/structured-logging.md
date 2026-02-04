# Structured Logging for Observability

This document explains how to use the structured logging system for monitoring, alerting, and control room dashboards.

## Overview

The `src.shared.structured_logging` module provides a standardized way to emit JSON-formatted log events that can be parsed by monitoring systems, dashboards, and alerting tools.

### Key Features

- **JSON-structured events** - Machine-parseable logs for automated analysis
- **Trace ID correlation** - Track related events across request lifecycle
- **Phase tracking** - Categorize events by workflow phase (discovery, extraction, export)
- **Built-in metrics** - Automatic aggregation of success rates, latencies, error counts
- **Heartbeat events** - Progress monitoring and stall detection
- **Multiple event types** - Request/response, errors, rate limits, checkpoints, retries

## Quick Start

```python
from src.shared.structured_logging import StructuredLogger, MetricsAggregator

# Initialize logger and metrics
logger = StructuredLogger(retailer='verizon')
metrics = MetricsAggregator()

# Track a request
start = time.time()
response = session.get(url)
latency_ms = (time.time() - start) * 1000

logger.log_request(url, response.status_code, latency_ms)
metrics.add_request(response.status_code, latency_ms)

# Emit heartbeat for progress
logger.log_heartbeat(stores_processed=100, phase='extraction')

# Get metrics summary
summary = metrics.get_summary()
print(f"Success rate: {summary['success_rate_pct']}%")
```

## Log Event Schema

All log events are emitted as JSON with this structure:

```json
{
  "timestamp": "2026-02-04T23:26:25.288117Z",
  "trace_id": "436ebe89",
  "retailer": "verizon",
  "phase": "extraction",
  "event": "request_end",
  "url": "https://example.com/store/123",
  "status": 200,
  "latency_ms": 150.5
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | string | Yes | ISO 8601 timestamp (UTC) |
| `trace_id` | string | Yes | 8-char UUID for request correlation |
| `retailer` | string | Yes | Retailer name |
| `phase` | string | Yes | Workflow phase |
| `event` | string | Yes | Event type |
| `url` | string | No | Request URL |
| `status` | int | No | HTTP status code |
| `latency_ms` | float | No | Request latency in milliseconds |
| `retry_count` | int | No | Number of retries |
| `store_count` | int | No | Number of stores processed |
| `error` | string | No | Error message |
| `metadata` | object | No | Additional context |

## Event Types

### REQUEST_END
Emitted when an HTTP request completes (success or failure).

```python
logger.log_request(
    url='https://example.com/store/123',
    status=200,
    latency_ms=150.5,
    retry_count=0,  # Optional, only if retried
    phase='extraction'
)
```

**Log Level**: DEBUG (200), WARNING (429, 4xx), ERROR (5xx)

### HEARTBEAT
Emitted periodically to show progress and detect stalls.

```python
logger.log_heartbeat(
    stores_processed=100,
    phase='extraction',
    metadata={'checkpoint_saved': True}  # Optional
)
```

**Recommendation**: Emit every 50-100 stores processed.

**Log Level**: INFO

### ERROR
Emitted when an error occurs.

```python
logger.log_error(
    error_message='Connection timeout',
    phase='extraction',
    url='https://example.com/store/123',  # Optional
    metadata={'retry_attempts': 3}  # Optional
)
```

**Log Level**: ERROR

### RETRY
Emitted when retrying a failed request.

```python
logger.log_retry(
    url='https://example.com/store/123',
    attempt=2,
    max_retries=3,
    reason='429 rate limit',
    phase='extraction'
)
```

**Log Level**: WARNING

### RATE_LIMIT
Emitted when encountering rate limits.

```python
logger.log_rate_limit(
    url='https://example.com/store/123',
    wait_time=30.0,  # seconds
    phase='extraction'
)
```

**Log Level**: WARNING

### PHASE_START / PHASE_END
Emitted at phase boundaries.

```python
logger.log_phase_start('discovery')

# ... do work ...

logger.log_phase_end(
    phase='discovery',
    store_count=500,
    metadata=metrics.get_summary()  # Optional
)
```

**Log Level**: INFO

**Note**: If you log both start and end, the end event will automatically include `duration_ms` in metadata.

### CHECKPOINT
Emitted when saving/loading checkpoints.

```python
logger.log_checkpoint(
    checkpoint_type='save',
    phase='extraction',
    metadata={'stores_saved': 100}
)
```

**Log Level**: INFO

## Phases

Standard workflow phases:

- `initialization` - Setup, configuration loading
- `discovery` - Finding store URLs
- `extraction` - Scraping store details
- `validation` - Validating scraped data
- `export` - Exporting to files
- `cleanup` - Cleanup, resource release

Use `Phase` enum for type safety:

```python
from src.shared.structured_logging import Phase

logger.log_phase_start(Phase.DISCOVERY.value)
```

## Metrics Aggregation

The `MetricsAggregator` tracks request statistics:

```python
metrics = MetricsAggregator()

# Track requests
metrics.add_request(status=200, latency_ms=150.5)
metrics.add_request(status=429, latency_ms=300.0, retries=2)
metrics.add_request(status=500, latency_ms=1000.0)

# Get summary
summary = metrics.get_summary()
```

### Summary Fields

```python
{
    'total_requests': 100,
    'success_rate_pct': 95.0,
    'avg_latency_ms': 175.5,
    'p95_latency_ms': 450.0,
    'client_errors': 3,      # 4xx count
    'server_errors': 2,      # 5xx count
    'rate_limits': 1,        # 429 count
    'total_retries': 5,
    'avg_retries': 1.67
}
```

### Reset Metrics

```python
metrics.reset()  # Clear all counters
```

## Integration Patterns

### Pattern 1: Wrapper Function

Wrap `get_with_retry` to add logging:

```python
def get_with_retry_logged(session, url, logger, metrics, **kwargs):
    start = time.time()
    response = get_with_retry(session, url, **kwargs)
    latency_ms = (time.time() - start) * 1000

    if response:
        logger.log_request(url, response.status_code, latency_ms)
        metrics.add_request(response.status_code, latency_ms)

    return response
```

### Pattern 2: Scraper Integration

Add to scraper `run()` function:

```python
def run(session, retailer_config, retailer: str, **kwargs) -> dict:
    logger = StructuredLogger(retailer=retailer)
    metrics = MetricsAggregator()

    logger.log_phase_start(Phase.DISCOVERY.value)

    # Discover URLs...

    logger.log_phase_end(Phase.DISCOVERY.value, store_count=len(urls))
    logger.log_phase_start(Phase.EXTRACTION.value)

    stores = []
    for i, url in enumerate(urls):
        start = time.time()
        response = get_with_retry(session, url)
        latency_ms = (time.time() - start) * 1000

        if response:
            logger.log_request(url, response.status_code, latency_ms)
            metrics.add_request(response.status_code, latency_ms)

            # Process response...
            stores.append(store_data)

            # Heartbeat every 50 stores
            if (i + 1) % 50 == 0:
                logger.log_heartbeat(len(stores), Phase.EXTRACTION.value)

    summary = metrics.get_summary()
    logger.log_phase_end(Phase.EXTRACTION.value, len(stores), metadata=summary)

    return {
        'stores': stores,
        'count': len(stores),
        'metrics': summary,
        'trace_id': logger.trace_id
    }
```

### Pattern 3: Error Handling

```python
try:
    response = get_with_retry(session, url)
    if response:
        logger.log_request(url, response.status_code, latency_ms)
    else:
        logger.log_error(
            error_message='Request failed after retries',
            phase='extraction',
            url=url
        )
except Exception as e:
    logger.log_error(
        error_message=str(e),
        phase='extraction',
        url=url,
        metadata={'exception_type': type(e).__name__}
    )
    raise
```

## Control Room Dashboard Integration

The structured logs can be parsed for real-time monitoring:

### Stall Detection

Parse heartbeat events. If no heartbeat for > 5 minutes, alert:

```bash
# Example: Find last heartbeat for retailer
grep '"event": "heartbeat"' scraper.log | grep '"retailer": "verizon"' | tail -1
```

### Success Rate Monitoring

Track success rate by parsing `request_end` events:

```bash
# Count success vs failure
grep '"event": "request_end"' scraper.log | jq '.status' | \
  awk '{if ($1 == 200) success++; else fail++} END {print "Success:", success, "Fail:", fail}'
```

### Latency Alerts

Alert on P95 latency > threshold:

```bash
# Extract latencies and calculate percentile
grep '"event": "request_end"' scraper.log | jq '.latency_ms' | sort -n
```

### Error Rate

Track error rate by parsing error events:

```bash
# Count errors in last hour
grep '"event": "error"' scraper.log | \
  jq -r 'select(.timestamp > "'$(date -u -v-1H -Iseconds)'") | .'
```

## Trace ID Correlation

All events from a single scraping run share a trace ID:

```bash
# Find all events for a specific run
grep '"trace_id": "436ebe89"' scraper.log | jq .
```

This allows:
- End-to-end request tracing
- Debugging specific runs
- Performance analysis per run

## Best Practices

1. **Always emit heartbeats** - Every 50-100 stores for progress monitoring
2. **Log phase boundaries** - Makes it easy to see where time is spent
3. **Include metadata** - Add context like checkpoint status, batch size, etc.
4. **Use appropriate log levels** - 200=DEBUG, 429=WARNING, 5xx=ERROR
5. **Track metrics per phase** - Create separate aggregators for discovery vs extraction
6. **Include trace_id in results** - Return trace_id so users can correlate logs
7. **Reset metrics between phases** - Prevents mixing discovery and extraction stats

## Example Output

```json
{"timestamp": "2026-02-04T23:26:25.288117Z", "trace_id": "436ebe89", "retailer": "verizon", "phase": "discovery", "event": "phase_start"}
{"timestamp": "2026-02-04T23:26:27.523456Z", "trace_id": "436ebe89", "retailer": "verizon", "phase": "discovery", "event": "request_end", "url": "https://www.verizon.com/stores/state/maryland/", "status": 200, "latency_ms": 234.5}
{"timestamp": "2026-02-04T23:26:30.789012Z", "trace_id": "436ebe89", "retailer": "verizon", "phase": "discovery", "event": "phase_end", "store_count": 150, "metadata": {"duration_ms": 5500.89}}
{"timestamp": "2026-02-04T23:26:30.789123Z", "trace_id": "436ebe89", "retailer": "verizon", "phase": "extraction", "event": "phase_start"}
{"timestamp": "2026-02-04T23:26:31.123456Z", "trace_id": "436ebe89", "retailer": "verizon", "phase": "extraction", "event": "request_end", "url": "https://www.verizon.com/stores/maryland/baltimore/store-123/", "status": 200, "latency_ms": 178.3}
{"timestamp": "2026-02-04T23:26:45.234567Z", "trace_id": "436ebe89", "retailer": "verizon", "phase": "extraction", "event": "heartbeat", "store_count": 50}
{"timestamp": "2026-02-04T23:27:02.345678Z", "trace_id": "436ebe89", "retailer": "verizon", "phase": "extraction", "event": "heartbeat", "store_count": 100}
{"timestamp": "2026-02-04T23:27:19.456789Z", "trace_id": "436ebe89", "retailer": "verizon", "phase": "extraction", "event": "phase_end", "store_count": 150, "metadata": {"total_requests": 150, "success_rate_pct": 98.67, "avg_latency_ms": 182.4, "p95_latency_ms": 456.7, "duration_ms": 48667.56}}
```

## See Also

- [Example Integration](../examples/structured_logging_integration.py) - Working code examples
- [Test Suite](../tests/test_structured_logging.py) - Comprehensive test coverage
- [Issue #152](https://github.com/vmud/retail-store-scraper/issues/152) - Original feature request
