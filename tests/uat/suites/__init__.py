"""
UAT Test Suites

This package contains UAT test suites for the Retail Store Scraper.
Each suite focuses on a specific area of functionality.
"""

from .init import InitSuite
from .status import StatusSuite
from .control import ControlSuite
from .config import ConfigSuite
from .logs import LogsSuite
from .history import HistorySuite
from .error import ErrorSuite
from .perf import PerfSuite
from .proxy import ProxySuite

# Export all suites
__all__ = [
    "InitSuite",
    "StatusSuite",
    "ControlSuite",
    "ConfigSuite",
    "LogsSuite",
    "HistorySuite",
    "ErrorSuite",
    "PerfSuite",
    "ProxySuite",
]

# Suite execution order (by priority)
SUITE_ORDER = [
    # Critical (must pass)
    "InitSuite",
    "StatusSuite",
    "ControlSuite",
    "ErrorSuite",
    # High priority
    "ConfigSuite",
    "LogsSuite",
    "ProxySuite",
    # Medium priority
    "HistorySuite",
    "PerfSuite",
]
