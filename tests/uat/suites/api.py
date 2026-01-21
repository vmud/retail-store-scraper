"""
API Test Suite - API Contract Verification Tests

Tests API response structure and contracts.

Test Cases:
- API-001: Status API Contract
- API-002: Config API Contract
- API-003: Runs API Contract
- API-004: Control API Contracts
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


class APISuite:
    """API Contract Test Suite"""

    SUITE_ID = "API"
    SUITE_NAME = "API Contracts"
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
                id="API-001",
                name="Status API Contract",
                description="Verify /api/status response structure",
                steps=[
                    "Call GET /api/status",
                    "Verify summary object structure",
                    "Verify retailers object structure",
                    "Check each retailer has required fields",
                ],
                pass_criteria=[
                    "summary has total_stores, active_retailers, total_retailers",
                    "retailers has all 6 retailer keys",
                    "Each retailer has status, progress, stats, phases",
                ],
            ),
            TestCase(
                id="API-002",
                name="Config API Contract",
                description="Verify /api/config response structure",
                steps=[
                    "Call GET /api/config",
                    "Verify response has path and content",
                    "Verify content is valid YAML string",
                ],
                pass_criteria=[
                    "Response has 'path' string",
                    "Response has 'content' string",
                    "Content contains 'retailers:' key",
                ],
            ),
            TestCase(
                id="API-003",
                name="Runs API Contract",
                description="Verify /api/runs/{retailer} response structure",
                steps=[
                    "Call GET /api/runs/verizon",
                    "Verify response structure",
                    "Check runs array items have required fields",
                ],
                pass_criteria=[
                    "Response has 'retailer', 'runs', 'count'",
                    "runs is an array",
                    "Each run has run_id, status fields",
                ],
            ),
            TestCase(
                id="API-004",
                name="Control API Contracts",
                description="Verify scraper control API response structures",
                steps=[
                    "Test /api/scraper/start response",
                    "Test /api/scraper/stop response",
                    "Test /api/scraper/restart response",
                ],
                pass_criteria=[
                    "Start returns retailer and message on success",
                    "Stop returns stopped array for 'all'",
                    "Error responses have 'error' field",
                ],
            ),
        ]

    async def run_api_001(
        self,
        api_call: Callable,
    ) -> TestResult:
        """API-001: Status API Contract"""
        test_id = "API-001"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            response = await api_call("GET", "/api/status")
            timer.stop()

            self.assertions.equals(
                response.get("status_code", 200),
                200,
                "Should return 200"
            )

            data = response.get("data", response)

            # Verify summary structure
            self.assertions.has_key(data, "summary", "Should have summary")
            summary = data.get("summary", {})
            self.assertions.has_keys(
                summary,
                ["total_stores", "active_retailers", "total_retailers"],
                "Summary should have required fields"
            )

            # Verify retailers structure
            self.assertions.has_key(data, "retailers", "Should have retailers")
            retailers = data.get("retailers", {})

            expected_retailers = self.config.retailers
            for retailer_id in expected_retailers:
                self.assertions.has_key(
                    retailers,
                    retailer_id,
                    f"Should have {retailer_id}"
                )

                retailer_data = retailers.get(retailer_id, {})
                self.assertions.has_keys(
                    retailer_data,
                    ["status", "progress"],
                    f"Retailer {retailer_id} should have status and progress"
                )

                # Verify progress structure
                progress = retailer_data.get("progress", {})
                self.assertions.has_keys(
                    progress,
                    ["percentage", "text"],
                    f"Retailer {retailer_id} progress should have percentage and text"
                )

            return TestResult(
                test_id=test_id,
                name="Status API Contract",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Status API Contract",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Status API Contract",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_api_002(
        self,
        api_call: Callable,
    ) -> TestResult:
        """API-002: Config API Contract"""
        test_id = "API-002"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            response = await api_call("GET", "/api/config")
            timer.stop()

            self.assertions.equals(
                response.get("status_code", 200),
                200,
                "Should return 200"
            )

            data = response.get("data", response)

            # Verify structure
            self.assertions.has_key(data, "path", "Should have path")
            self.assertions.has_key(data, "content", "Should have content")

            # Verify path is string
            self.assertions.true(
                isinstance(data.get("path"), str),
                "path should be a string"
            )

            # Verify content contains YAML structure
            content = data.get("content", "")
            self.assertions.contains(
                content,
                "retailers:",
                "Content should contain 'retailers:' YAML key"
            )

            return TestResult(
                test_id=test_id,
                name="Config API Contract",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Config API Contract",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Config API Contract",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_api_003(
        self,
        api_call: Callable,
    ) -> TestResult:
        """API-003: Runs API Contract"""
        test_id = "API-003"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            response = await api_call("GET", "/api/runs/verizon")
            timer.stop()

            self.assertions.equals(
                response.get("status_code", 200),
                200,
                "Should return 200"
            )

            data = response.get("data", response)

            # Verify structure
            self.assertions.has_keys(
                data,
                ["retailer", "runs", "count"],
                "Should have retailer, runs, and count"
            )

            # Verify retailer matches
            self.assertions.equals(
                data.get("retailer"),
                "verizon",
                "Retailer should be 'verizon'"
            )

            # Verify runs is array
            runs = data.get("runs", [])
            self.assertions.true(
                isinstance(runs, list),
                "runs should be an array"
            )

            # Verify count matches
            self.assertions.equals(
                data.get("count"),
                len(runs),
                "count should match runs array length"
            )

            return TestResult(
                test_id=test_id,
                name="Runs API Contract",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Runs API Contract",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Runs API Contract",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_api_004(
        self,
        api_call: Callable,
    ) -> TestResult:
        """API-004: Control API Contracts"""
        test_id = "API-004"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Test error responses have correct structure
            # Start without retailer
            start_error = await api_call("POST", "/api/scraper/start", {})
            self.assertions.has_key(
                start_error.get("data", start_error),
                "error",
                "Start error should have 'error' field"
            )

            # Stop without retailer
            stop_error = await api_call("POST", "/api/scraper/stop", {})
            self.assertions.has_key(
                stop_error.get("data", stop_error),
                "error",
                "Stop error should have 'error' field"
            )

            # Restart without retailer
            restart_error = await api_call("POST", "/api/scraper/restart", {})
            timer.stop()

            self.assertions.has_key(
                restart_error.get("data", restart_error),
                "error",
                "Restart error should have 'error' field"
            )

            return TestResult(
                test_id=test_id,
                name="Control API Contracts",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Control API Contracts",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Control API Contracts",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_all(
        self,
        api_call: Callable,
    ) -> SuiteResult:
        """Run all tests in this suite"""
        self.results.start_time = datetime.now()

        self.results.tests.append(await self.run_api_001(api_call))
        self.results.tests.append(await self.run_api_002(api_call))
        self.results.tests.append(await self.run_api_003(api_call))
        self.results.tests.append(await self.run_api_004(api_call))

        self.results.end_time = datetime.now()
        return self.results
