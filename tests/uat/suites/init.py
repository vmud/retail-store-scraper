"""
INIT Test Suite - Dashboard Initialization Tests

Tests that the dashboard loads correctly with all components.

Test Cases:
- INIT-001: Dashboard page loads successfully
- INIT-002: All DOM elements present
- INIT-003: Initial API data fetch works
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Callable, Any
from datetime import datetime

from ..helpers import (
    UATConfig,
    SuiteResult,
    TestResult,
    TestStatus,
    Priority,
    Assertions,
    SnapshotParser,
    Timer,
)


@dataclass
class TestCase:
    """Test case definition"""
    id: str
    name: str
    description: str
    steps: list[str]
    pass_criteria: list[str]


class InitSuite:
    """Dashboard Initialization Test Suite"""

    SUITE_ID = "INIT"
    SUITE_NAME = "Dashboard Initialization"
    PRIORITY = Priority.CRITICAL

    def __init__(self, config: Optional[UATConfig] = None):
        self.config = config or UATConfig()
        self.assertions = Assertions()
        self.results = SuiteResult(
            suite_id=self.SUITE_ID,
            name=self.SUITE_NAME,
            priority=self.PRIORITY,
        )

    def get_test_cases(self) -> list[TestCase]:
        """Return all test cases in this suite"""
        return [
            TestCase(
                id="INIT-001",
                name="Dashboard Page Load",
                description="Verify dashboard page loads successfully",
                steps=[
                    "Navigate to dashboard URL",
                    "Wait for page to load",
                    "Capture page snapshot",
                    "Verify response status 200",
                ],
                pass_criteria=[
                    "Response status 200",
                    "Page title contains 'R.S.S' or 'Command Center'",
                    "Load time < 3 seconds",
                ],
            ),
            TestCase(
                id="INIT-002",
                name="All DOM Elements Present",
                description="Verify all critical DOM elements are rendered",
                steps=[
                    "Capture page snapshot",
                    "Verify #app element exists",
                    "Verify .header element exists",
                    "Verify #operations-grid exists",
                    "Verify 6 retailer cards rendered",
                ],
                pass_criteria=[
                    "#app element present",
                    ".header element visible",
                    "#operations-grid element present",
                    "6 retailer cards with [data-retailer] attribute",
                ],
            ),
            TestCase(
                id="INIT-003",
                name="Initial Data Fetch",
                description="Verify initial API data is fetched and displayed",
                steps=[
                    "Wait for initial polling (5 seconds)",
                    "Capture page snapshot",
                    "Verify status data displayed",
                    "Check for console errors",
                ],
                pass_criteria=[
                    "No console errors",
                    "Status data populated in cards",
                    "Metrics strip shows values (not '--')",
                ],
            ),
        ]

    async def run_init_001(
        self,
        navigate: Callable,
        snapshot: Callable,
        console_messages: Callable,
    ) -> TestResult:
        """INIT-001: Dashboard Page Load"""
        test_id = "INIT-001"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Step 1: Navigate to dashboard
            nav_result = await navigate(self.config.base_url)

            # Step 2: Capture snapshot
            snap_result = await snapshot()

            timer.stop()

            # Step 3: Verify page loaded
            parser = SnapshotParser(snap_result)

            # Check for key elements
            self.assertions.true(
                parser.element_exists("R.S.S") or parser.element_exists("Command Center"),
                "Page should contain dashboard branding"
            )

            # Check for console errors
            console = await console_messages("error")
            self.assertions.equals(
                len(console.get("messages", [])),
                0,
                "Should have no console errors on load"
            )

            # Check load time
            self.assertions.less_than(
                timer.elapsed_ms,
                self.config.timeouts["page_load"],
                f"Page should load within {self.config.timeouts['page_load']}ms"
            )

            return TestResult(
                test_id=test_id,
                name="Dashboard Page Load",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Dashboard Page Load",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Dashboard Page Load",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_init_002(
        self,
        snapshot: Callable,
        evaluate: Callable,
    ) -> TestResult:
        """INIT-002: All DOM Elements Present"""
        test_id = "INIT-002"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Capture snapshot
            snap_result = await snapshot()
            parser = SnapshotParser(snap_result)

            # Use evaluate to check DOM elements directly
            check_script = """() => {
                return {
                    app: !!document.getElementById('app'),
                    header: !!document.querySelector('.header'),
                    operationsGrid: !!document.getElementById('operations-grid'),
                    retailerCards: document.querySelectorAll('[data-retailer]').length,
                    configBtn: !!document.getElementById('config-btn'),
                    metricsGrid: !!document.getElementById('metrics-grid'),
                    toastContainer: !!document.getElementById('toast-container'),
                }
            }"""

            dom_check = await evaluate(check_script)
            timer.stop()

            # Verify all elements
            self.assertions.true(dom_check["app"], "#app element should exist")
            self.assertions.true(dom_check["header"], ".header element should exist")
            self.assertions.true(dom_check["operationsGrid"], "#operations-grid should exist")
            self.assertions.equals(
                dom_check["retailerCards"],
                6,
                "Should have 6 retailer cards"
            )
            self.assertions.true(dom_check["configBtn"], "#config-btn should exist")
            self.assertions.true(dom_check["metricsGrid"], "#metrics-grid should exist")
            self.assertions.true(dom_check["toastContainer"], "#toast-container should exist")

            return TestResult(
                test_id=test_id,
                name="All DOM Elements Present",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="All DOM Elements Present",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="All DOM Elements Present",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_init_003(
        self,
        wait_for: Callable,
        snapshot: Callable,
        evaluate: Callable,
        console_messages: Callable,
    ) -> TestResult:
        """INIT-003: Initial Data Fetch"""
        test_id = "INIT-003"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Wait for initial polling cycle
            await wait_for(time=6)  # Wait 6 seconds (> 5s polling interval)

            # Check metrics are populated
            metrics_script = """() => {
                const stores = document.getElementById('metric-stores');
                const requests = document.getElementById('metric-requests');
                return {
                    storesValue: stores?.textContent || '',
                    requestsValue: requests?.textContent || '',
                }
            }"""

            metrics = await evaluate(metrics_script)

            timer.stop()

            # Verify data is populated (not just '--')
            self.assertions.not_equals(
                metrics["storesValue"],
                "--",
                "Stores metric should be populated"
            )

            # Check for console errors
            console = await console_messages("error")
            console_errors = console.get("messages", [])

            self.assertions.equals(
                len(console_errors),
                0,
                f"Should have no console errors, got: {console_errors}"
            )

            return TestResult(
                test_id=test_id,
                name="Initial Data Fetch",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Initial Data Fetch",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Initial Data Fetch",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_all(
        self,
        navigate: Callable,
        snapshot: Callable,
        evaluate: Callable,
        wait_for: Callable,
        console_messages: Callable,
    ) -> SuiteResult:
        """Run all tests in this suite"""
        self.results.start_time = datetime.now()

        # Run tests in order
        self.results.tests.append(
            await self.run_init_001(navigate, snapshot, console_messages)
        )

        self.results.tests.append(
            await self.run_init_002(snapshot, evaluate)
        )

        self.results.tests.append(
            await self.run_init_003(wait_for, snapshot, evaluate, console_messages)
        )

        self.results.end_time = datetime.now()
        return self.results
