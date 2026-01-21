"""
UAT Helper Utilities

Shared utilities for browser automation and API interaction in UAT tests.
These helpers abstract MCP Playwright tool usage for cleaner test code.
"""

from __future__ import annotations

import re
import time
import json
import yaml
import asyncio
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime
from enum import Enum


class TestStatus(Enum):
    """Test execution status"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class Priority(Enum):
    """Test priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TestResult:
    """Captures result of a single test case"""
    test_id: str
    name: str
    status: TestStatus
    duration_ms: float
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    console_errors: list[str] = field(default_factory=list)
    api_response: Optional[dict] = None
    assertions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "screenshot_path": self.screenshot_path,
            "console_errors": self.console_errors,
            "assertions": self.assertions,
        }


@dataclass
class SuiteResult:
    """Captures result of a test suite"""
    suite_id: str
    name: str
    priority: Priority
    tests: list[TestResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def passed(self) -> int:
        return len([t for t in self.tests if t.status == TestStatus.PASSED])

    @property
    def failed(self) -> int:
        return len([t for t in self.tests if t.status == TestStatus.FAILED])

    @property
    def skipped(self) -> int:
        return len([t for t in self.tests if t.status == TestStatus.SKIPPED])

    @property
    def total(self) -> int:
        return len(self.tests)

    @property
    def duration_ms(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return sum(t.duration_ms for t in self.tests)

    def to_dict(self) -> dict:
        return {
            "suite_id": self.suite_id,
            "name": self.name,
            "priority": self.priority.value,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "total": self.total,
            "duration_ms": self.duration_ms,
            "tests": [t.to_dict() for t in self.tests],
        }


class UATConfig:
    """Loads and provides access to UAT configuration"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        with open(config_path, "r") as f:
            self._config = yaml.safe_load(f)

    @property
    def base_url(self) -> str:
        return self._config["application"]["base_url"]

    @property
    def retailers(self) -> list[str]:
        return self._config["retailers"]

    @property
    def timeouts(self) -> dict:
        return self._config["timeouts"]

    @property
    def performance(self) -> dict:
        return self._config["performance"]

    @property
    def selectors(self) -> dict:
        return self._config["selectors"]

    @property
    def api_endpoints(self) -> dict:
        return self._config["api_endpoints"]

    @property
    def suites(self) -> dict:
        return self._config["suites"]

    @property
    def reporting(self) -> dict:
        return self._config["reporting"]

    def get_selector(self, name: str, **kwargs) -> str:
        """Get a selector with optional placeholder replacement"""
        selector = self.selectors.get(name, name)
        for key, value in kwargs.items():
            selector = selector.replace("{" + key + "}", value)
        return selector

    def get_endpoint(self, name: str, **kwargs) -> str:
        """Get an API endpoint with optional placeholder replacement"""
        endpoint = self.api_endpoints.get(name, name)
        for key, value in kwargs.items():
            endpoint = endpoint.replace("{" + key + "}", value)
        return self.base_url + endpoint


class Assertions:
    """Assertion helpers that record results"""

    def __init__(self):
        self.results: list[dict] = []

    def _record(self, passed: bool, assertion_type: str, message: str,
                expected: Any = None, actual: Any = None):
        self.results.append({
            "passed": passed,
            "type": assertion_type,
            "message": message,
            "expected": expected,
            "actual": actual,
        })
        if not passed:
            raise AssertionError(message)

    def reset(self):
        self.results = []

    def equals(self, actual: Any, expected: Any, message: str = ""):
        """Assert two values are equal"""
        passed = actual == expected
        msg = message or f"Expected {expected}, got {actual}"
        self._record(passed, "equals", msg, expected, actual)

    def not_equals(self, actual: Any, not_expected: Any, message: str = ""):
        """Assert two values are not equal"""
        passed = actual != not_expected
        msg = message or f"Expected value to not equal {not_expected}"
        self._record(passed, "not_equals", msg, f"not {not_expected}", actual)

    def true(self, value: bool, message: str = ""):
        """Assert value is truthy"""
        passed = bool(value)
        msg = message or f"Expected truthy value, got {value}"
        self._record(passed, "true", msg, True, value)

    def false(self, value: bool, message: str = ""):
        """Assert value is falsy"""
        passed = not bool(value)
        msg = message or f"Expected falsy value, got {value}"
        self._record(passed, "false", msg, False, value)

    def contains(self, container: Any, item: Any, message: str = ""):
        """Assert container includes item"""
        passed = item in container
        msg = message or f"Expected {container} to contain {item}"
        self._record(passed, "contains", msg, item, container)

    def not_contains(self, container: Any, item: Any, message: str = ""):
        """Assert container does not include item"""
        passed = item not in container
        msg = message or f"Expected {container} to not contain {item}"
        self._record(passed, "not_contains", msg, f"not {item}", container)

    def matches(self, value: str, pattern: str, message: str = ""):
        """Assert string matches regex pattern"""
        passed = bool(re.search(pattern, value))
        msg = message or f"Expected {value} to match pattern {pattern}"
        self._record(passed, "matches", msg, pattern, value)

    def greater_than(self, actual: float, expected: float, message: str = ""):
        """Assert actual is greater than expected"""
        passed = actual > expected
        msg = message or f"Expected {actual} > {expected}"
        self._record(passed, "greater_than", msg, f"> {expected}", actual)

    def less_than(self, actual: float, expected: float, message: str = ""):
        """Assert actual is less than expected"""
        passed = actual < expected
        msg = message or f"Expected {actual} < {expected}"
        self._record(passed, "less_than", msg, f"< {expected}", actual)

    def in_range(self, actual: float, min_val: float, max_val: float, message: str = ""):
        """Assert actual is within range [min_val, max_val]"""
        passed = min_val <= actual <= max_val
        msg = message or f"Expected {actual} to be in range [{min_val}, {max_val}]"
        self._record(passed, "in_range", msg, f"[{min_val}, {max_val}]", actual)

    def is_none(self, value: Any, message: str = ""):
        """Assert value is None"""
        passed = value is None
        msg = message or f"Expected None, got {value}"
        self._record(passed, "is_none", msg, None, value)

    def is_not_none(self, value: Any, message: str = ""):
        """Assert value is not None"""
        passed = value is not None
        msg = message or "Expected value to not be None"
        self._record(passed, "is_not_none", msg, "not None", value)

    def has_key(self, obj: dict, key: str, message: str = ""):
        """Assert dict has key"""
        passed = key in obj
        msg = message or f"Expected dict to have key '{key}'"
        self._record(passed, "has_key", msg, key, list(obj.keys()))

    def has_keys(self, obj: dict, keys: list[str], message: str = ""):
        """Assert dict has all keys"""
        missing = [k for k in keys if k not in obj]
        passed = len(missing) == 0
        msg = message or f"Expected dict to have keys {keys}, missing {missing}"
        self._record(passed, "has_keys", msg, keys, list(obj.keys()))

    def status_code(self, response: dict, expected: int, message: str = ""):
        """Assert HTTP status code"""
        actual = response.get("status_code", response.get("status"))
        passed = actual == expected
        msg = message or f"Expected status {expected}, got {actual}"
        self._record(passed, "status_code", msg, expected, actual)

    def response_time(self, duration_ms: float, max_ms: float, message: str = ""):
        """Assert response time is within threshold"""
        passed = duration_ms <= max_ms
        msg = message or f"Expected response time <= {max_ms}ms, got {duration_ms}ms"
        self._record(passed, "response_time", msg, f"<= {max_ms}ms", f"{duration_ms}ms")


class SnapshotParser:
    """Parses Playwright accessibility snapshots to extract element references"""

    def __init__(self, snapshot: str):
        self.snapshot = snapshot
        self._elements = self._parse_elements()

    def _parse_elements(self) -> list[dict]:
        """Parse snapshot into list of element dictionaries"""
        elements = []
        lines = self.snapshot.split('\n')

        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue

            # Extract reference (e.g., [ref=42])
            ref_match = re.search(r'\[ref=(\d+)\]', line)
            ref = ref_match.group(1) if ref_match else None

            # Extract element type and name
            type_match = re.search(r'- ([\w]+)(?:\s+"([^"]*)")?', line)
            if type_match:
                elem_type = type_match.group(1)
                elem_name = type_match.group(2) or ""
                elements.append({
                    "ref": ref,
                    "type": elem_type,
                    "name": elem_name,
                    "raw": line.strip(),
                })

        return elements

    def find_by_text(self, text: str, elem_type: Optional[str] = None) -> Optional[str]:
        """Find element reference by text content"""
        for elem in self._elements:
            if text.lower() in elem["name"].lower():
                if elem_type is None or elem["type"] == elem_type:
                    return elem["ref"]
        return None

    def find_by_type(self, elem_type: str) -> list[str]:
        """Find all element references of a given type"""
        return [elem["ref"] for elem in self._elements
                if elem["type"] == elem_type and elem["ref"]]

    def find_button(self, text: str) -> Optional[str]:
        """Find button reference by text"""
        return self.find_by_text(text, "button")

    def find_link(self, text: str) -> Optional[str]:
        """Find link reference by text"""
        return self.find_by_text(text, "link")

    def find_textbox(self, name: str = "") -> Optional[str]:
        """Find textbox reference"""
        for elem in self._elements:
            if elem["type"] == "textbox":
                if not name or name.lower() in elem["name"].lower():
                    return elem["ref"]
        return None

    def element_exists(self, text: str) -> bool:
        """Check if element with text exists in snapshot"""
        return any(text.lower() in elem["name"].lower() for elem in self._elements)

    def get_text_content(self) -> str:
        """Get all text content from snapshot"""
        return " ".join(elem["name"] for elem in self._elements if elem["name"])


class Timer:
    """Simple timer for measuring durations"""

    def __init__(self):
        self._start: Optional[float] = None
        self._end: Optional[float] = None

    def start(self):
        self._start = time.time()
        self._end = None

    def stop(self) -> float:
        self._end = time.time()
        return self.elapsed_ms

    @property
    def elapsed_ms(self) -> float:
        end = self._end or time.time()
        if self._start is None:
            return 0
        return (end - self._start) * 1000

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()


def format_duration(ms: float) -> str:
    """Format duration in human-readable form"""
    if ms < 1000:
        return f"{ms:.0f}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    else:
        minutes = int(ms / 60000)
        seconds = (ms % 60000) / 1000
        return f"{minutes}m {seconds:.0f}s"


def sanitize_filename(name: str) -> str:
    """Sanitize string for use as filename"""
    return re.sub(r'[^\w\-_]', '_', name)


def get_timestamp() -> str:
    """Get current timestamp for reports"""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def load_json_file(path: str) -> dict:
    """Load JSON file safely"""
    with open(path, 'r') as f:
        return json.load(f)


def save_json_file(path: str, data: dict):
    """Save dict to JSON file"""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)


# Valid YAML config for testing configuration save
VALID_TEST_CONFIG = """retailers:
  verizon:
    name: Verizon
    enabled: true
    base_url: https://www.verizon.com
    discovery_method: html_crawl
    min_delay: 2.0
    max_delay: 5.0
    timeout: 30
    checkpoint_interval: 50
  att:
    name: AT&T
    enabled: true
    base_url: https://www.att.com
    discovery_method: sitemap
    min_delay: 2.0
    max_delay: 5.0
    timeout: 30
    checkpoint_interval: 50
  target:
    name: Target
    enabled: true
    base_url: https://www.target.com
    discovery_method: sitemap_gzip
    min_delay: 2.0
    max_delay: 5.0
    timeout: 30
    checkpoint_interval: 50
  tmobile:
    name: T-Mobile
    enabled: true
    base_url: https://www.t-mobile.com
    discovery_method: sitemap_paginated
    min_delay: 2.0
    max_delay: 5.0
    timeout: 30
    checkpoint_interval: 50
  walmart:
    name: Walmart
    enabled: true
    base_url: https://www.walmart.com
    discovery_method: sitemap_gzip
    min_delay: 2.0
    max_delay: 5.0
    timeout: 30
    checkpoint_interval: 50
  bestbuy:
    name: Best Buy
    enabled: false
    base_url: https://www.bestbuy.com
    discovery_method: sitemap
    min_delay: 2.0
    max_delay: 5.0
    timeout: 30
    checkpoint_interval: 50
"""

# Invalid YAML for testing validation
INVALID_YAML_SYNTAX = """retailers:
  verizon:
    - invalid syntax [
"""

INVALID_CONFIG_MISSING_RETAILERS = """something_else:
  value: test
"""

INVALID_CONFIG_BAD_URL = """retailers:
  verizon:
    name: Verizon
    enabled: true
    base_url: not-a-valid-url
    discovery_method: html_crawl
"""
