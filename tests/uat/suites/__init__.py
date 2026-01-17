"""
UAT Test Suites

This package contains all UAT test suites for the Retail Store Scraper Dashboard.
Each suite focuses on a specific area of functionality.
"""

from .init import InitSuite
from .status import StatusSuite
from .control import ControlSuite
from .config import ConfigSuite
from .logs import LogsSuite
from .history import HistorySuite
from .ui import UISuite
from .error import ErrorSuite
from .api import APISuite
from .perf import PerfSuite

# Export all suites
__all__ = [
    "InitSuite",
    "StatusSuite",
    "ControlSuite",
    "ConfigSuite",
    "LogsSuite",
    "HistorySuite",
    "UISuite",
    "ErrorSuite",
    "APISuite",
    "PerfSuite",
]

# Suite execution order (by priority)
SUITE_ORDER = [
    # Critical (must pass)
    "InitSuite",
    "StatusSuite",
    "ControlSuite",
    "ErrorSuite",
    "APISuite",
    # High priority
    "ConfigSuite",
    "LogsSuite",
    "UISuite",
    # Medium priority
    "HistorySuite",
    "PerfSuite",
]
