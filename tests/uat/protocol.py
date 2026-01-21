"""
UAT Protocol - Main Test Orchestration

This module provides the main UAT runner that orchestrates all test suites
and integrates with MCP Playwright tools for browser automation.

Usage:
    protocol = UATProtocol()
    results = await protocol.run_all()
    protocol.print_report()
    protocol.save_report()

For use with Claude Code and MCP tools:
    The protocol is designed to be executed by an AI agent using Playwright
    MCP tools (browser_navigate, browser_click, browser_snapshot, etc.)
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Any

from .helpers import (
    UATConfig,
    TestStatus,
    Priority,
    SuiteResult,
    Timer,
    format_duration,
    get_timestamp,
)
from .report import ReportGenerator, print_report
from .suites import (
    InitSuite,
    StatusSuite,
    ControlSuite,
    ConfigSuite,
    LogsSuite,
    HistorySuite,
    UISuite,
    ErrorSuite,
    APISuite,
    PerfSuite,
    ProxySuite,
)


class UATProtocol:
    """
    Main UAT Protocol Runner

    Orchestrates all test suites and provides a unified interface for
    running UAT tests against the retail store scraper dashboard.
    """

    def __init__(self, config: Optional[UATConfig] = None):
        """
        Initialize the UAT Protocol.

        Args:
            config: Optional UATConfig instance. If not provided, loads from default path.
        """
        self.config = config or UATConfig()
        self.report = ReportGenerator(self.config)

        # Initialize all test suites
        self.suites = {
            "init": InitSuite(self.config),
            "status": StatusSuite(self.config),
            "control": ControlSuite(self.config),
            "config": ConfigSuite(self.config),
            "logs": LogsSuite(self.config),
            "history": HistorySuite(self.config),
            "ui": UISuite(self.config),
            "error": ErrorSuite(self.config),
            "api": APISuite(self.config),
            "perf": PerfSuite(self.config),
            "proxy": ProxySuite(self.config),
        }

        # MCP tool functions (to be set by caller)
        self._navigate: Optional[Callable] = None
        self._snapshot: Optional[Callable] = None
        self._click: Optional[Callable] = None
        self._type: Optional[Callable] = None
        self._evaluate: Optional[Callable] = None
        self._wait_for: Optional[Callable] = None
        self._press_key: Optional[Callable] = None
        self._console_messages: Optional[Callable] = None
        self._network_requests: Optional[Callable] = None
        self._api_call: Optional[Callable] = None
        self._api_call_raw: Optional[Callable] = None

    def set_browser_tools(
        self,
        navigate: Callable,
        snapshot: Callable,
        click: Callable,
        type_text: Callable,
        evaluate: Callable,
        wait_for: Callable,
        press_key: Callable,
        console_messages: Callable,
        network_requests: Callable,
    ):
        """
        Set MCP Playwright browser tool functions.

        Args:
            navigate: browser_navigate function
            snapshot: browser_snapshot function
            click: browser_click function
            type_text: browser_type function
            evaluate: browser_evaluate function
            wait_for: browser_wait_for function
            press_key: browser_press_key function
            console_messages: browser_console_messages function
            network_requests: browser_network_requests function
        """
        self._navigate = navigate
        self._snapshot = snapshot
        self._click = click
        self._type = type_text
        self._evaluate = evaluate
        self._wait_for = wait_for
        self._press_key = press_key
        self._console_messages = console_messages
        self._network_requests = network_requests

    def set_api_tools(
        self,
        api_call: Callable,
        api_call_raw: Optional[Callable] = None,
    ):
        """
        Set API testing functions.

        Args:
            api_call: Function for making API calls with JSON body
                      Signature: async (method, endpoint, body=None) -> dict
            api_call_raw: Function for making raw API calls with custom content-type
                          Signature: async (method, endpoint, body=None, content_type=None) -> dict
        """
        self._api_call = api_call
        self._api_call_raw = api_call_raw or api_call

    async def setup(self):
        """
        Setup phase - verify prerequisites.

        Returns:
            bool: True if setup successful
        """
        print("=" * 60)
        print("UAT PROTOCOL SETUP")
        print("=" * 60)
        print(f"Target: {self.config.base_url}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Set environment info for report
        self.report.set_environment({
            "base_url": self.config.base_url,
            "timestamp": get_timestamp(),
            "retailers": self.config.retailers,
        })

        # Verify server is running by making a status API call
        if self._api_call:
            try:
                response = await self._api_call("GET", "/api/status")
                if response.get("status_code", 200) == 200:
                    print("[OK] Flask server is responding")
                    return True
                else:
                    print(f"[ERROR] Flask server returned status {response.get('status_code')}")
                    return False
            except Exception as e:
                print(f"[ERROR] Could not connect to Flask server: {e}")
                return False

        print("[WARN] No API call function set, skipping server check")
        return True

    async def run_suite(self, suite_name: str) -> Optional[SuiteResult]:
        """
        Run a single test suite.

        Args:
            suite_name: Name of the suite (init, status, control, etc.)

        Returns:
            SuiteResult or None if suite not found
        """
        suite = self.suites.get(suite_name)
        if not suite:
            print(f"[ERROR] Unknown suite: {suite_name}")
            return None

        print(f"\nRunning {suite.SUITE_NAME} suite ({suite.SUITE_ID})...")
        print("-" * 40)

        try:
            # Call appropriate run_all based on suite type
            if suite_name == "init":
                result = await suite.run_all(
                    self._navigate,
                    self._snapshot,
                    self._evaluate,
                    self._wait_for,
                    self._console_messages,
                )
            elif suite_name == "status":
                result = await suite.run_all(
                    self._api_call,
                    self._evaluate,
                    self._wait_for,
                    self._network_requests,
                )
            elif suite_name == "control":
                result = await suite.run_all(
                    self._snapshot,
                    self._click,
                    self._wait_for,
                    self._evaluate,
                    self._api_call,
                )
            elif suite_name == "config":
                result = await suite.run_all(
                    self._api_call,
                    self._snapshot,
                    self._click,
                    self._wait_for,
                    self._evaluate,
                )
            elif suite_name == "logs":
                result = await suite.run_all(
                    self._api_call,
                    self._evaluate,
                )
            elif suite_name == "history":
                result = await suite.run_all(
                    self._api_call,
                    self._evaluate,
                    self._snapshot,
                    self._click,
                    self._wait_for,
                )
            elif suite_name == "ui":
                result = await suite.run_all(
                    self._snapshot,
                    self._click,
                    self._press_key,
                    self._wait_for,
                    self._evaluate,
                )
            elif suite_name == "error":
                result = await suite.run_all(
                    self._api_call,
                    self._api_call_raw,
                )
            elif suite_name == "api":
                result = await suite.run_all(
                    self._api_call,
                )
            elif suite_name == "perf":
                result = await suite.run_all(
                    self._navigate,
                    self._api_call,
                    self._snapshot,
                    self._click,
                    self._wait_for,
                    self._evaluate,
                )
            elif suite_name == "proxy":
                result = await suite.run_all(
                    self._api_call,
                )
            else:
                print(f"[ERROR] Suite {suite_name} not implemented")
                return None

            # Print suite summary
            status_icon = "[PASS]" if result.failed == 0 else "[FAIL]"
            print(f"{status_icon} {result.suite_id}: {result.passed}/{result.total} passed")

            return result

        except Exception as e:
            print(f"[ERROR] Suite {suite_name} failed with exception: {e}")
            return None

    async def run_critical_suites(self) -> list[SuiteResult]:
        """
        Run only critical priority suites.

        Returns:
            List of SuiteResults
        """
        critical_suites = ["init", "status", "control", "error", "api"]
        results = []

        for suite_name in critical_suites:
            result = await self.run_suite(suite_name)
            if result:
                results.append(result)
                self.report.add_suite(result)

        return results

    async def run_all(self) -> list[SuiteResult]:
        """
        Run all test suites in priority order.

        Returns:
            List of SuiteResults
        """
        self.report.start()

        # Setup phase
        if not await self.setup():
            print("\n[ABORT] Setup failed, cannot proceed with tests")
            self.report.finish()
            return []

        print("\n" + "=" * 60)
        print("EXECUTING TEST SUITES")
        print("=" * 60)

        # Define suite execution order
        suite_order = [
            # Critical (must pass)
            "init",
            "status",
            "control",
            "error",
            "api",
            # High priority
            "config",
            "logs",
            "ui",
            "proxy",
            # Medium priority
            "history",
            "perf",
        ]

        results = []
        for suite_name in suite_order:
            result = await self.run_suite(suite_name)
            if result:
                results.append(result)
                self.report.add_suite(result)

        self.report.finish()
        return results

    async def cleanup(self):
        """
        Cleanup phase - stop any running scrapers, restore config.
        """
        print("\n" + "=" * 60)
        print("CLEANUP")
        print("=" * 60)

        # Stop all running scrapers
        if self._api_call:
            try:
                await self._api_call("POST", "/api/scraper/stop", {"retailer": "all"})
                print("[OK] Stopped all scrapers")
            except Exception as e:
                print(f"[WARN] Could not stop scrapers: {e}")

        print("[OK] Cleanup complete")

    def print_summary(self):
        """Print test execution summary to console."""
        print_report(self.report)

    def save_report(self, output_dir: Optional[str] = None) -> dict[str, str]:
        """
        Save reports to files.

        Args:
            output_dir: Optional output directory path

        Returns:
            Dict mapping format name to file path
        """
        paths = self.report.save(output_dir)
        print(f"\nReports saved:")
        for fmt, path in paths.items():
            print(f"  {fmt}: {path}")
        return paths


# Standalone execution helpers for pytest integration

def create_api_call_wrapper(base_url: str) -> Callable:
    """
    Create an API call wrapper for testing without browser.

    Args:
        base_url: Dashboard base URL

    Returns:
        Async function for making API calls
    """
    import aiohttp

    async def api_call(method: str, endpoint: str, body: dict = None) -> dict:
        url = f"{base_url}{endpoint}"
        async with aiohttp.ClientSession() as session:
            kwargs = {"headers": {"Content-Type": "application/json"}}
            if body is not None:
                kwargs["json"] = body

            async with session.request(method, url, **kwargs) as response:
                try:
                    data = await response.json()
                except Exception:
                    data = await response.text()

                return {
                    "status_code": response.status,
                    "data": data,
                }

    return api_call


def create_api_call_raw_wrapper(base_url: str) -> Callable:
    """
    Create a raw API call wrapper for testing with custom content types.

    Args:
        base_url: Dashboard base URL

    Returns:
        Async function for making raw API calls
    """
    import aiohttp

    async def api_call_raw(
        method: str,
        endpoint: str,
        body: str = None,
        content_type: str = "application/json"
    ) -> dict:
        url = f"{base_url}{endpoint}"
        async with aiohttp.ClientSession() as session:
            kwargs = {"headers": {"Content-Type": content_type}}
            if body is not None:
                kwargs["data"] = body

            async with session.request(method, url, **kwargs) as response:
                try:
                    data = await response.json()
                except Exception:
                    data = await response.text()

                return {
                    "status_code": response.status,
                    "data": data,
                }

    return api_call_raw


# Example usage documentation
USAGE_EXAMPLE = """
# Running UAT Protocol with Claude Code

## Method 1: Agent-Driven Execution

The UAT protocol is designed to be executed by an AI agent using MCP Playwright tools.
The agent should:

1. Start by navigating to the dashboard:
   browser_navigate(url="http://localhost:5001")

2. Capture snapshots to understand page state:
   browser_snapshot()

3. Execute test steps by clicking elements:
   browser_click(element="Start button", ref="...")

4. Verify results via API calls or DOM evaluation:
   browser_evaluate(function="() => document.getElementById('metric-stores').textContent")

5. Generate report with results

## Method 2: Pytest Integration

```python
import pytest
from tests.uat import UATProtocol

@pytest.fixture
async def protocol():
    p = UATProtocol()
    p.set_api_tools(
        create_api_call_wrapper("http://localhost:5001"),
        create_api_call_raw_wrapper("http://localhost:5001")
    )
    return p

@pytest.mark.asyncio
async def test_api_contracts(protocol):
    result = await protocol.run_suite("api")
    assert result.failed == 0
```

## Method 3: Standalone Script

```python
import asyncio
from tests.uat import UATProtocol

async def main():
    protocol = UATProtocol()

    # Set up mock/real MCP tool functions
    protocol.set_api_tools(
        create_api_call_wrapper("http://localhost:5001")
    )

    # Run all tests
    results = await protocol.run_all()

    # Print and save report
    protocol.print_summary()
    protocol.save_report()

asyncio.run(main())
```
"""
