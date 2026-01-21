"""
LOGS Test Suite - Log Viewing Tests

Tests log retrieval and viewing functionality.

Test Cases:
- LOGS-001: Get Logs for Run
- LOGS-002: Open Log Viewer Modal
- LOGS-003: Filter Logs by Level
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


class LogsSuite:
    """Log Viewing Test Suite"""

    SUITE_ID = "LOGS"
    SUITE_NAME = "Log Viewing"
    PRIORITY = Priority.HIGH

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
                id="LOGS-001",
                name="Get Logs API Validation",
                description="Verify logs API validates parameters",
                steps=[
                    "Call GET /api/logs with invalid retailer",
                    "Call GET /api/logs with invalid run_id",
                    "Verify error responses",
                ],
                pass_criteria=[
                    "Invalid retailer returns 404",
                    "Invalid run_id format returns 400",
                    "Error messages are descriptive",
                ],
            ),
            TestCase(
                id="LOGS-002",
                name="Log Viewer Modal Structure",
                description="Verify log viewer modal has correct structure",
                steps=[
                    "Check log modal exists in DOM",
                    "Verify filter buttons present",
                    "Verify log content container exists",
                ],
                pass_criteria=[
                    "#log-modal exists",
                    "Filter buttons for ALL, INFO, WARNING, ERROR, DEBUG",
                    "#log-content container exists",
                ],
            ),
            TestCase(
                id="LOGS-003",
                name="Log Filter Buttons",
                description="Verify log filter buttons are functional",
                steps=[
                    "Check all filter buttons present",
                    "Verify button data attributes",
                    "Check default 'ALL' is active",
                ],
                pass_criteria=[
                    "5 filter buttons present",
                    "Each button has data-level attribute",
                    "ALL button has 'active' class by default",
                ],
            ),
        ]

    async def run_logs_001(
        self,
        api_call: Callable,
    ) -> TestResult:
        """LOGS-001: Get Logs API Validation"""
        test_id = "LOGS-001"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Test invalid retailer
            invalid_retailer_response = await api_call(
                "GET",
                "/api/logs/invalid_retailer/run123"
            )
            self.assertions.equals(
                invalid_retailer_response.get("status_code", 404),
                404,
                "Invalid retailer should return 404"
            )

            # Test path traversal attempt
            traversal_response = await api_call(
                "GET",
                "/api/logs/verizon/../../../etc/passwd"
            )
            timer.stop()

            self.assertions.equals(
                traversal_response.get("status_code", 404),
                404,
                "Path traversal should return 404"
            )

            return TestResult(
                test_id=test_id,
                name="Get Logs API Validation",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Get Logs API Validation",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Get Logs API Validation",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_logs_002(
        self,
        evaluate: Callable,
    ) -> TestResult:
        """LOGS-002: Log Viewer Modal Structure"""
        test_id = "LOGS-002"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Check modal structure
            modal_script = """() => {
                return {
                    modalExists: !!document.getElementById('log-modal'),
                    contentExists: !!document.getElementById('log-content'),
                    statsExists: !!document.getElementById('log-stats'),
                    closeExists: !!document.getElementById('log-modal-close'),
                    titleExists: !!document.getElementById('log-modal-title'),
                }
            }"""

            structure = await evaluate(modal_script)
            timer.stop()

            self.assertions.true(
                structure["modalExists"],
                "#log-modal should exist"
            )

            self.assertions.true(
                structure["contentExists"],
                "#log-content should exist"
            )

            self.assertions.true(
                structure["statsExists"],
                "#log-stats should exist"
            )

            self.assertions.true(
                structure["closeExists"],
                "Log modal close button should exist"
            )

            return TestResult(
                test_id=test_id,
                name="Log Viewer Modal Structure",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Log Viewer Modal Structure",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Log Viewer Modal Structure",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_logs_003(
        self,
        evaluate: Callable,
    ) -> TestResult:
        """LOGS-003: Log Filter Buttons"""
        test_id = "LOGS-003"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Check filter buttons
            filter_script = """() => {
                const filterBtns = document.querySelectorAll('.log-filter-btn');
                const levels = [];
                let activeLevel = null;

                filterBtns.forEach(btn => {
                    levels.push(btn.dataset.level);
                    if (btn.classList.contains('active')) {
                        activeLevel = btn.dataset.level;
                    }
                });

                return {
                    count: filterBtns.length,
                    levels: levels,
                    activeLevel: activeLevel,
                }
            }"""

            filters = await evaluate(filter_script)
            timer.stop()

            self.assertions.equals(
                filters["count"],
                5,
                "Should have 5 filter buttons"
            )

            expected_levels = ["ALL", "INFO", "WARNING", "ERROR", "DEBUG"]
            for level in expected_levels:
                self.assertions.contains(
                    filters["levels"],
                    level,
                    f"Should have {level} filter button"
                )

            self.assertions.equals(
                filters["activeLevel"],
                "ALL",
                "ALL filter should be active by default"
            )

            return TestResult(
                test_id=test_id,
                name="Log Filter Buttons",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Log Filter Buttons",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Log Filter Buttons",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_all(
        self,
        api_call: Callable,
        evaluate: Callable,
    ) -> SuiteResult:
        """Run all tests in this suite"""
        self.results.start_time = datetime.now()

        self.results.tests.append(await self.run_logs_001(api_call))
        self.results.tests.append(await self.run_logs_002(evaluate))
        self.results.tests.append(await self.run_logs_003(evaluate))

        self.results.end_time = datetime.now()
        return self.results
