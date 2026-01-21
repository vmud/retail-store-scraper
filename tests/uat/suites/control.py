"""
CONTROL Test Suite - Scraper Control Operation Tests

Tests start/stop/restart operations for scrapers.

Test Cases:
- CONTROL-001: Start Individual Scraper
- CONTROL-002: Stop Running Scraper
- CONTROL-003: Restart Completed Scraper
- CONTROL-004: Start All Scrapers
- CONTROL-005: Stop All Scrapers
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


class ControlSuite:
    """Scraper Control Test Suite"""

    SUITE_ID = "CONTROL"
    SUITE_NAME = "Scraper Control"
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
                id="CONTROL-001",
                name="Start Individual Scraper",
                description="Start a single retailer scraper via UI",
                steps=[
                    "Find START button for idle retailer",
                    "Click START button",
                    "Wait for toast notification",
                    "Verify status changes to RUNNING",
                ],
                pass_criteria=[
                    "POST /api/scraper/start called",
                    "Toast shows success message",
                    "Card status updates within 2s",
                    "START button becomes disabled",
                ],
            ),
            TestCase(
                id="CONTROL-002",
                name="Stop Running Scraper",
                description="Stop a running scraper via UI",
                steps=[
                    "Ensure scraper is running",
                    "Click STOP button",
                    "Wait for status change",
                    "Verify status no longer RUNNING",
                ],
                pass_criteria=[
                    "POST /api/scraper/stop called",
                    "Graceful shutdown within 30s",
                    "STOP button becomes disabled",
                    "START button becomes enabled",
                ],
            ),
            TestCase(
                id="CONTROL-003",
                name="Restart Scraper",
                description="Restart a completed scraper",
                steps=[
                    "Find RESTART button (visible when complete)",
                    "Click RESTART button",
                    "Verify scraper restarts",
                ],
                pass_criteria=[
                    "POST /api/scraper/restart called",
                    "Status changes to RUNNING",
                    "Progress resets or continues",
                ],
            ),
            TestCase(
                id="CONTROL-004",
                name="Start API Validation",
                description="Verify start API validates input",
                steps=[
                    "POST /api/scraper/start with empty body",
                    "POST /api/scraper/start with invalid retailer",
                    "Verify error responses",
                ],
                pass_criteria=[
                    "Empty body returns 400",
                    "Invalid retailer returns 400",
                    "Error message in response",
                ],
            ),
            TestCase(
                id="CONTROL-005",
                name="Stop API Validation",
                description="Verify stop API validates input",
                steps=[
                    "POST /api/scraper/stop with empty body",
                    "POST /api/scraper/stop with invalid retailer",
                    "Verify error responses",
                ],
                pass_criteria=[
                    "Empty body returns 400",
                    "Invalid retailer returns 400",
                    "Error message in response",
                ],
            ),
        ]

    async def run_control_001(
        self,
        snapshot: Callable,
        click: Callable,
        wait_for: Callable,
        evaluate: Callable,
    ) -> TestResult:
        """CONTROL-001: Start Individual Scraper"""
        test_id = "CONTROL-001"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Find an idle retailer's start button
            find_start_script = """() => {
                const cards = document.querySelectorAll('[data-retailer]');
                for (const card of cards) {
                    const startBtn = card.querySelector('[data-action="start"]:not([disabled])');
                    if (startBtn) {
                        const retailer = card.dataset.retailer;
                        return { retailer, found: true };
                    }
                }
                return { retailer: null, found: false };
            }"""

            result = await evaluate(find_start_script)

            if not result["found"]:
                # Skip test if no idle scrapers
                return TestResult(
                    test_id=test_id,
                    name="Start Individual Scraper",
                    status=TestStatus.SKIPPED,
                    duration_ms=timer.elapsed_ms,
                    error_message="No idle scrapers available to test",
                )

            retailer = result["retailer"]

            # Get snapshot and find button
            snap = await snapshot()
            parser = SnapshotParser(snap)

            # Click the start button
            start_btn_ref = parser.find_button("START")
            if start_btn_ref:
                await click(f"START button for {retailer}", start_btn_ref)

            # Wait for toast and status update
            await wait_for(time=2)

            # Check toast appeared
            toast_script = """() => {
                const toasts = document.querySelectorAll('.toast');
                return toasts.length > 0;
            }"""
            has_toast = await evaluate(toast_script)
            timer.stop()

            self.assertions.true(has_toast, "Toast notification should appear")

            return TestResult(
                test_id=test_id,
                name="Start Individual Scraper",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Start Individual Scraper",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Start Individual Scraper",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_control_002(
        self,
        snapshot: Callable,
        click: Callable,
        wait_for: Callable,
        evaluate: Callable,
    ) -> TestResult:
        """CONTROL-002: Stop Running Scraper"""
        test_id = "CONTROL-002"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Find a running retailer's stop button
            find_stop_script = """() => {
                const cards = document.querySelectorAll('[data-retailer]');
                for (const card of cards) {
                    const stopBtn = card.querySelector('[data-action="stop"]:not([disabled])');
                    if (stopBtn) {
                        const retailer = card.dataset.retailer;
                        return { retailer, found: true };
                    }
                }
                return { retailer: null, found: false };
            }"""

            result = await evaluate(find_stop_script)

            if not result["found"]:
                # Skip test if no running scrapers
                return TestResult(
                    test_id=test_id,
                    name="Stop Running Scraper",
                    status=TestStatus.SKIPPED,
                    duration_ms=timer.elapsed_ms,
                    error_message="No running scrapers available to test",
                )

            retailer = result["retailer"]

            # Get snapshot and find button
            snap = await snapshot()
            parser = SnapshotParser(snap)

            # Click the stop button
            stop_btn_ref = parser.find_button("STOP")
            if stop_btn_ref:
                await click(f"STOP button for {retailer}", stop_btn_ref)

            # Wait for status update
            await wait_for(time=2)

            timer.stop()

            # Verify stop button is now disabled
            verify_script = f"""() => {{
                const card = document.querySelector('[data-retailer="{retailer}"]');
                const stopBtn = card?.querySelector('[data-action="stop"]');
                return stopBtn?.disabled || false;
            }}"""

            is_disabled = await evaluate(verify_script)
            self.assertions.true(is_disabled, "STOP button should be disabled after click")

            return TestResult(
                test_id=test_id,
                name="Stop Running Scraper",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Stop Running Scraper",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Stop Running Scraper",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_control_003(
        self,
        snapshot: Callable,
        click: Callable,
        wait_for: Callable,
        evaluate: Callable,
    ) -> TestResult:
        """CONTROL-003: Restart Scraper"""
        test_id = "CONTROL-003"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Find a restart button (only visible when complete)
            find_restart_script = """() => {
                const restartBtn = document.querySelector('[data-action="restart"]');
                if (restartBtn) {
                    const card = restartBtn.closest('[data-retailer]');
                    return { retailer: card?.dataset.retailer, found: true };
                }
                return { retailer: null, found: false };
            }"""

            result = await evaluate(find_restart_script)

            if not result["found"]:
                return TestResult(
                    test_id=test_id,
                    name="Restart Scraper",
                    status=TestStatus.SKIPPED,
                    duration_ms=timer.elapsed_ms,
                    error_message="No completed scrapers with RESTART button",
                )

            retailer = result["retailer"]

            # Get snapshot and find button
            snap = await snapshot()
            parser = SnapshotParser(snap)

            # Click restart button
            restart_btn_ref = parser.find_button("RESTART")
            if restart_btn_ref:
                await click(f"RESTART button for {retailer}", restart_btn_ref)

            # Wait for response
            await wait_for(time=2)
            timer.stop()

            return TestResult(
                test_id=test_id,
                name="Restart Scraper",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Restart Scraper",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Restart Scraper",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_control_004(
        self,
        api_call: Callable,
    ) -> TestResult:
        """CONTROL-004: Start API Validation"""
        test_id = "CONTROL-004"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Test empty body
            empty_response = await api_call("POST", "/api/scraper/start", {})
            self.assertions.equals(
                empty_response.get("status_code", 400),
                400,
                "Empty body should return 400"
            )

            empty_data = empty_response.get("data", empty_response)
            self.assertions.has_key(empty_data, "error", "Should have error message")

            # Test invalid retailer
            invalid_response = await api_call(
                "POST",
                "/api/scraper/start",
                {"retailer": "invalid_retailer"}
            )
            timer.stop()

            self.assertions.equals(
                invalid_response.get("status_code", 400),
                400,
                "Invalid retailer should return 400"
            )

            return TestResult(
                test_id=test_id,
                name="Start API Validation",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Start API Validation",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Start API Validation",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_control_005(
        self,
        api_call: Callable,
    ) -> TestResult:
        """CONTROL-005: Stop API Validation"""
        test_id = "CONTROL-005"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Test empty body
            empty_response = await api_call("POST", "/api/scraper/stop", {})
            self.assertions.equals(
                empty_response.get("status_code", 400),
                400,
                "Empty body should return 400"
            )

            empty_data = empty_response.get("data", empty_response)
            self.assertions.has_key(empty_data, "error", "Should have error message")

            # Test invalid retailer
            invalid_response = await api_call(
                "POST",
                "/api/scraper/stop",
                {"retailer": "invalid_retailer"}
            )
            timer.stop()

            self.assertions.equals(
                invalid_response.get("status_code", 400),
                400,
                "Invalid retailer should return 400"
            )

            return TestResult(
                test_id=test_id,
                name="Stop API Validation",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Stop API Validation",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Stop API Validation",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_all(
        self,
        snapshot: Callable,
        click: Callable,
        wait_for: Callable,
        evaluate: Callable,
        api_call: Callable,
    ) -> SuiteResult:
        """Run all tests in this suite"""
        self.results.start_time = datetime.now()

        self.results.tests.append(
            await self.run_control_001(snapshot, click, wait_for, evaluate)
        )
        self.results.tests.append(
            await self.run_control_002(snapshot, click, wait_for, evaluate)
        )
        self.results.tests.append(
            await self.run_control_003(snapshot, click, wait_for, evaluate)
        )
        self.results.tests.append(await self.run_control_004(api_call))
        self.results.tests.append(await self.run_control_005(api_call))

        self.results.end_time = datetime.now()
        return self.results
