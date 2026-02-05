"""Sentry.io integration for error monitoring and performance tracking.

This module initializes Sentry SDK with project-specific configuration,
including custom tags for retailer context and filtering of sensitive data.

Usage:
    from src.shared.sentry_integration import init_sentry, capture_scraper_error

    # Initialize at application startup (run.py)
    init_sentry()

    # Capture errors with retailer context
    capture_scraper_error(exception, retailer="verizon", extra={"url": url})
"""

import os
import logging
from typing import Any, Dict, Optional

# Lazy import to avoid errors if sentry-sdk not installed
_sentry_sdk = None
_sentry_initialized = False

logger = logging.getLogger(__name__)


def _get_sentry_sdk():
    """Lazy load sentry-sdk to make it optional."""
    global _sentry_sdk
    if _sentry_sdk is None:
        try:
            import sentry_sdk
            _sentry_sdk = sentry_sdk
        except ImportError:
            _sentry_sdk = False  # Mark as unavailable
    return _sentry_sdk if _sentry_sdk else None


def init_sentry(
    dsn: Optional[str] = None,
    environment: Optional[str] = None,
    release: Optional[str] = None,
    traces_sample_rate: Optional[float] = None,
) -> bool:
    """Initialize Sentry SDK with project configuration.

    Args:
        dsn: Sentry DSN (defaults to SENTRY_DSN env var)
        environment: Environment name (defaults to SENTRY_ENVIRONMENT or 'development')
        release: Release version (defaults to SENTRY_RELEASE or git hash)
        traces_sample_rate: Performance monitoring sample rate (0.0 to 1.0)

    Returns:
        True if Sentry was initialized, False if disabled or unavailable
    """
    global _sentry_initialized

    if _sentry_initialized:
        return True

    sentry_sdk = _get_sentry_sdk()
    if sentry_sdk is None:
        logger.debug("Sentry SDK not installed, skipping initialization")
        return False

    # Get configuration from environment or parameters
    dsn = dsn or os.getenv("SENTRY_DSN", "")
    if not dsn:
        logger.debug("SENTRY_DSN not set, Sentry disabled")
        return False

    environment = environment or os.getenv("SENTRY_ENVIRONMENT", "development")
    release = release or os.getenv("SENTRY_RELEASE") or _get_git_release()

    # Default to 10% sampling for performance monitoring
    if traces_sample_rate is None:
        traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            traces_sample_rate=traces_sample_rate,
            # Integrations
            integrations=[],
            # Filter sensitive data
            before_send=_before_send,
            before_send_transaction=_before_send_transaction,
            # Additional options
            send_default_pii=False,  # Don't send personally identifiable info
            attach_stacktrace=True,  # Always attach stack traces
            max_breadcrumbs=50,  # Limit breadcrumbs for performance
        )

        # Set default tags
        sentry_sdk.set_tag("project", "retail-store-scraper")

        _sentry_initialized = True
        logger.info(f"Sentry initialized (environment={environment}, release={release})")
        return True

    except Exception as e:
        logger.warning(f"Failed to initialize Sentry: {e}")
        return False


def _get_git_release() -> Optional[str]:
    """Get current git commit hash as release version."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _before_send(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Filter and modify events before sending to Sentry.

    Removes sensitive data like proxy credentials and API keys.
    """
    # Scrub sensitive data from exception messages
    if "exception" in event:
        for exception in event.get("exception", {}).get("values", []):
            if "value" in exception:
                exception["value"] = _scrub_sensitive_data(exception["value"])

    # Scrub breadcrumbs
    for breadcrumb in event.get("breadcrumbs", {}).get("values", []):
        if "message" in breadcrumb:
            breadcrumb["message"] = _scrub_sensitive_data(breadcrumb["message"])

    return event


def _before_send_transaction(
    event: Dict[str, Any], hint: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Filter transactions before sending to Sentry."""
    return event


def _scrub_sensitive_data(text: str) -> str:
    """Remove sensitive data from text."""
    if not isinstance(text, str):
        return text

    # Patterns to redact
    import re

    # Redact proxy credentials in URLs (user:pass@host)
    text = re.sub(r"://[^:]+:[^@]+@", "://[REDACTED]@", text)

    # Redact common API key patterns
    text = re.sub(r"(api[_-]?key|password|secret|token)=[^&\s]+", r"\1=[REDACTED]", text, flags=re.IGNORECASE)

    # Redact Oxylabs credentials
    text = re.sub(r"customer_\w+", "[OXYLABS_USER]", text)

    return text


def set_retailer_context(retailer: str) -> None:
    """Set the current retailer as Sentry context.

    Call this when starting to process a retailer.

    Args:
        retailer: Retailer name (e.g., 'verizon', 'target')
    """
    sentry_sdk = _get_sentry_sdk()
    if sentry_sdk and _sentry_initialized:
        sentry_sdk.set_tag("retailer", retailer)
        sentry_sdk.set_context("scraper", {"retailer": retailer})


def capture_scraper_error(
    exception: Exception,
    retailer: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Capture an exception with scraper context.

    Args:
        exception: The exception to capture
        retailer: Retailer name for context
        extra: Additional context data (e.g., URL, store_id)

    Returns:
        Sentry event ID if captured, None otherwise
    """
    sentry_sdk = _get_sentry_sdk()
    if not sentry_sdk or not _sentry_initialized:
        return None

    with sentry_sdk.push_scope() as scope:
        if retailer:
            scope.set_tag("retailer", retailer)

        if extra:
            # Scrub sensitive data from extra context
            safe_extra = {}
            for key, value in extra.items():
                if isinstance(value, str):
                    safe_extra[key] = _scrub_sensitive_data(value)
                else:
                    safe_extra[key] = value
            scope.set_context("scraper_context", safe_extra)

        return sentry_sdk.capture_exception(exception)


def capture_message(
    message: str,
    level: str = "info",
    retailer: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Capture a message with context.

    Args:
        message: Message to capture
        level: Severity level ('debug', 'info', 'warning', 'error', 'fatal')
        retailer: Retailer name for context
        extra: Additional context data

    Returns:
        Sentry event ID if captured, None otherwise
    """
    sentry_sdk = _get_sentry_sdk()
    if not sentry_sdk or not _sentry_initialized:
        return None

    with sentry_sdk.push_scope() as scope:
        if retailer:
            scope.set_tag("retailer", retailer)
        if extra:
            scope.set_context("extra", extra)

        return sentry_sdk.capture_message(message, level=level)


def add_breadcrumb(
    message: str,
    category: str = "scraper",
    level: str = "info",
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Add a breadcrumb for debugging context.

    Breadcrumbs provide a trail of events leading up to an error.

    Args:
        message: Breadcrumb message
        category: Category (e.g., 'http', 'scraper', 'export')
        level: Severity level
        data: Additional data to attach
    """
    sentry_sdk = _get_sentry_sdk()
    if sentry_sdk and _sentry_initialized:
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data,
        )


def start_transaction(name: str, op: str = "scraper") -> Any:
    """Start a performance monitoring transaction.

    Use as a context manager:
        with start_transaction("scrape_verizon", op="scraper.run") as transaction:
            # ... scraping code ...

    Args:
        name: Transaction name (e.g., 'scrape_verizon')
        op: Operation type (e.g., 'scraper.run', 'http.request')

    Returns:
        Transaction object (or no-op if Sentry not initialized)
    """
    sentry_sdk = _get_sentry_sdk()
    if sentry_sdk and _sentry_initialized:
        return sentry_sdk.start_transaction(name=name, op=op)

    # Return a no-op context manager if Sentry is not available
    from contextlib import nullcontext
    return nullcontext()


def flush(timeout: float = 2.0) -> None:
    """Flush pending events to Sentry.

    Call this before application exit to ensure all events are sent.

    Args:
        timeout: Maximum time to wait in seconds
    """
    sentry_sdk = _get_sentry_sdk()
    if sentry_sdk and _sentry_initialized:
        sentry_sdk.flush(timeout=timeout)
