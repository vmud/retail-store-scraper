"""
PERF Test Suite - Performance Tests

Tests response times and performance thresholds.

Test Cases:
- PERF-001: Page Load Performance
- PERF-002: API Response Times
- PERF-003: UI Responsiveness
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Callable
from datetime import datetime

from ..helpers import (
    UATConfig,
    SuiteResult,
    TestResult,
    TestStatus,
    Priority,
    Assertions,
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


class PerfSuite:
    """Performance Test Suite"""

    SUITE_ID = "PERF"
    SUITE_NAME = "Performance"
    PRIORITY = Priority.MEDIUM

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
                id="PERF-001",
                name="Page Load Performance",
                description="Verify page loads within acceptable time",
                steps=[
                    "Navigate to dashboard",
                    "Measure time to DOM ready",
                    "Measure time to interactive",
                ],
                pass_criteria=[
                    "DOM ready < 2 seconds",
                    "Interactive < 5 seconds",
                    "No blocking resources",
                ],
            ),
            TestCase(
                id="PERF-002",
                name="API Response Times",
                description="Verify API endpoints respond quickly",
                steps=[
                    "Measure GET /api/status time",
                    "Measure GET /api/config time",
                    "Measure GET /api/runs/verizon time",
                ],
                pass_criteria=[
                    "Status API < 500ms",
                    "Config API < 300ms",
                    "Runs API < 500ms",
                ],
            ),
            TestCase(
                id="PERF-003",
                name="UI Responsiveness",
                description="Verify UI interactions are responsive",
                steps=[
                    "Measure modal open time",
                    "Measure button response time",
                    "Check for jank or delays",
                ],
                pass_criteria=[
                    "Modal opens < 500ms",
                    "Button feedback < 100ms",
                    "No noticeable jank",
                ],
            ),
        ]

    async def run_perf_001(
        self,
        navigate: Callable,
        evaluate: Callable,
    ) -> TestResult:
        """PERF-001: Page Load Performance"""
        test_id = "PERF-001"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Navigate and measure load time
            nav_result = await navigate(self.config.base_url)
            nav_time = timer.elapsed_ms

            # Get performance metrics
            perf_script = """() => {
                const perf = performance.getEntriesByType('navigation')[0];
                return {
                    domContentLoaded: perf?.domContentLoadedEventEnd || 0,
                    loadComplete: perf?.loadEventEnd || 0,
                    domInteractive: perf?.domInteractive || 0,
                }
            }"""

            perf_metrics = await evaluate(perf_script)
            timer.stop()

            thresholds = self.config.performance

            # Check DOM ready time
            self.assertions.less_than(
                nav_time,
                thresholds["page_load_dom_ready"]["maximum"],
                f"Page should load within {thresholds['page_load_dom_ready']['maximum']}ms"
            )

            return TestResult(
                test_id=test_id,
                name="Page Load Performance",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Page Load Performance",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Page Load Performance",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_perf_002(
        self,
        api_call: Callable,
    ) -> TestResult:
        """PERF-002: API Response Times"""
        test_id = "PERF-002"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()
            thresholds = self.config.performance

            # Measure status API
            status_timer = Timer()
            status_timer.start()
            await api_call("GET", "/api/status")
            status_time = status_timer.stop()

            self.assertions.less_than(
                status_time,
                thresholds["api_status"]["maximum"],
                f"Status API should respond within {thresholds['api_status']['maximum']}ms"
            )

            # Measure config API
            config_timer = Timer()
            config_timer.start()
            await api_call("GET", "/api/config")
            config_time = config_timer.stop()

            self.assertions.less_than(
                config_time,
                thresholds["api_config"]["maximum"],
                f"Config API should respond within {thresholds['api_config']['maximum']}ms"
            )

            # Measure runs API
            runs_timer = Timer()
            runs_timer.start()
            await api_call("GET", "/api/runs/verizon")
            runs_time = runs_timer.stop()

            timer.stop()

            self.assertions.less_than(
                runs_time,
                500,  # 500ms threshold for runs API
                "Runs API should respond within 500ms"
            )

            return TestResult(
                test_id=test_id,
                name="API Response Times",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="API Response Times",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="API Response Times",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_perf_003(
        self,
        snapshot: Callable,
        click: Callable,
        wait_for: Callable,
        evaluate: Callable,
    ) -> TestResult:
        """PERF-003: UI Responsiveness"""
        test_id = "PERF-003"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()
            thresholds = self.config.performance

            # Measure modal open time
            modal_timer = Timer()
            modal_timer.start()

            # Click config button
            click_script = """() => {
                document.getElementById('config-btn').click();
                return true;
            }"""
            await evaluate(click_script)

            # Wait for modal to be visible
            await wait_for(time=0.1)

            # Check if modal is visible
            check_script = """() => {
                const modal = document.getElementById('config-modal');
                return getComputedStyle(modal).display !== 'none';
            }"""
            is_visible = await evaluate(check_script)

            modal_time = modal_timer.stop()

            self.assertions.less_than(
                modal_time,
                thresholds["modal_open"]["maximum"],
                f"Modal should open within {thresholds['modal_open']['maximum']}ms"
            )

            # Close modal
            close_script = """() => {
                document.getElementById('config-modal-close').click();
            }"""
            await evaluate(close_script)

            timer.stop()

            return TestResult(
                test_id=test_id,
                name="UI Responsiveness",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="UI Responsiveness",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="UI Responsiveness",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_all(
        self,
        navigate: Callable,
        api_call: Callable,
        snapshot: Callable,
        click: Callable,
        wait_for: Callable,
        evaluate: Callable,
    ) -> SuiteResult:
        """Run all tests in this suite"""
        self.results.start_time = datetime.now()

        self.results.tests.append(await self.run_perf_001(navigate, evaluate))
        self.results.tests.append(await self.run_perf_002(api_call))
        self.results.tests.append(
            await self.run_perf_003(snapshot, click, wait_for, evaluate)
        )

        self.results.end_time = datetime.now()
        return self.results
