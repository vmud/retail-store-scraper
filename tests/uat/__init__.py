"""
UAT Protocol Package

User Acceptance Testing protocol for the Retail Store Scraper Dashboard.
Provides automated validation using browser control tools and API testing.

Usage:
    from tests.uat import UATProtocol, UATConfig

    protocol = UATProtocol()
    results = await protocol.run_all()
    protocol.save_report()
"""

from .helpers import (
    UATConfig,
    TestStatus,
    Priority,
    TestResult,
    SuiteResult,
    Assertions,
    SnapshotParser,
    Timer,
    format_duration,
)
from .report import ReportGenerator, print_report
from .protocol import UATProtocol

__all__ = [
    # Main classes
    "UATProtocol",
    "UATConfig",
    "ReportGenerator",
    # Result types
    "TestStatus",
    "Priority",
    "TestResult",
    "SuiteResult",
    # Utilities
    "Assertions",
    "SnapshotParser",
    "Timer",
    "format_duration",
    "print_report",
]

__version__ = "1.0.0"
