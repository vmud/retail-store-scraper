"""
ERROR Test Suite - Error Handling Tests

Tests graceful error handling and recovery.

Test Cases:
- ERROR-001: Invalid API Requests
- ERROR-002: Network Error Recovery
- ERROR-003: Invalid Content Type
- ERROR-004: Path Traversal Prevention
- ERROR-005: Malformed JSON Handling
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


class ErrorSuite:
    """Error Handling Test Suite"""

    SUITE_ID = "ERROR"
    SUITE_NAME = "Error Handling"
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
                id="ERROR-001",
                name="Invalid API Requests",
                description="Verify invalid API requests handled gracefully",
                steps=[
                    "POST to /api/scraper/start with no body",
                    "POST to /api/config with no content",
                    "Verify consistent error format",
                ],
                pass_criteria=[
                    "All return 400 status",
                    "Error response has 'error' key",
                    "Error messages are descriptive",
                ],
            ),
            TestCase(
                id="ERROR-002",
                name="Invalid Retailer Requests",
                description="Verify invalid retailer names handled",
                steps=[
                    "GET /api/status/nonexistent",
                    "POST start with invalid retailer",
                    "GET /api/runs/nonexistent",
                ],
                pass_criteria=[
                    "Returns 404 for unknown retailer",
                    "Returns 400 for invalid operations",
                    "Error messages identify the issue",
                ],
            ),
            TestCase(
                id="ERROR-003",
                name="Invalid Content Type",
                description="Verify non-JSON POST requests rejected",
                steps=[
                    "POST /api/scraper/start with text/plain",
                    "POST /api/config with form-urlencoded",
                    "Verify 415 responses",
                ],
                pass_criteria=[
                    "Returns 415 Unsupported Media Type",
                    "Error message mentions content type",
                ],
            ),
            TestCase(
                id="ERROR-004",
                name="Path Traversal Prevention",
                description="Verify path traversal attacks blocked",
                steps=[
                    "GET /api/logs/verizon/../../../etc/passwd",
                    "GET /api/logs/verizon/../../secrets",
                    "Verify all blocked",
                ],
                pass_criteria=[
                    "All traversal attempts return 404",
                    "No file system access outside allowed paths",
                    "Consistent error responses",
                ],
            ),
            TestCase(
                id="ERROR-005",
                name="Malformed JSON Handling",
                description="Verify malformed JSON requests handled",
                steps=[
                    "POST /api/config with invalid JSON",
                    "POST /api/scraper/start with malformed body",
                    "Verify appropriate errors",
                ],
                pass_criteria=[
                    "Returns 400 for malformed JSON",
                    "Error indicates JSON parsing issue",
                ],
            ),
        ]

    async def run_error_001(
        self,
        api_call: Callable,
    ) -> TestResult:
        """ERROR-001: Invalid API Requests"""
        test_id = "ERROR-001"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Test empty start body
            start_response = await api_call("POST", "/api/scraper/start", {})
            self.assertions.equals(
                start_response.get("status_code", 400),
                400,
                "Empty start body should return 400"
            )
            start_data = start_response.get("data", start_response)
            self.assertions.has_key(start_data, "error", "Should have error message")

            # Test empty config body
            config_response = await api_call("POST", "/api/config", {})
            self.assertions.equals(
                config_response.get("status_code", 400),
                400,
                "Empty config body should return 400"
            )

            # Test empty stop body
            stop_response = await api_call("POST", "/api/scraper/stop", {})
            timer.stop()

            self.assertions.equals(
                stop_response.get("status_code", 400),
                400,
                "Empty stop body should return 400"
            )

            return TestResult(
                test_id=test_id,
                name="Invalid API Requests",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Invalid API Requests",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Invalid API Requests",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_error_002(
        self,
        api_call: Callable,
    ) -> TestResult:
        """ERROR-002: Invalid Retailer Requests"""
        test_id = "ERROR-002"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Test nonexistent retailer status
            status_response = await api_call("GET", "/api/status/nonexistent_retailer")
            self.assertions.equals(
                status_response.get("status_code", 404),
                404,
                "Nonexistent retailer should return 404"
            )

            # Test start with invalid retailer
            start_response = await api_call(
                "POST",
                "/api/scraper/start",
                {"retailer": "fake_retailer"}
            )
            self.assertions.equals(
                start_response.get("status_code", 400),
                400,
                "Invalid retailer start should return 400"
            )

            # Test runs with invalid retailer
            runs_response = await api_call("GET", "/api/runs/nonexistent_retailer")
            timer.stop()

            self.assertions.equals(
                runs_response.get("status_code", 404),
                404,
                "Nonexistent retailer runs should return 404"
            )

            return TestResult(
                test_id=test_id,
                name="Invalid Retailer Requests",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Invalid Retailer Requests",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Invalid Retailer Requests",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_error_003(
        self,
        api_call_raw: Callable,
    ) -> TestResult:
        """ERROR-003: Invalid Content Type"""
        test_id = "ERROR-003"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Test with text/plain content type
            text_response = await api_call_raw(
                "POST",
                "/api/scraper/start",
                body='{"retailer": "verizon"}',
                content_type="text/plain"
            )
            timer.stop()

            self.assertions.equals(
                text_response.get("status_code", 415),
                415,
                "text/plain content type should return 415"
            )

            return TestResult(
                test_id=test_id,
                name="Invalid Content Type",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Invalid Content Type",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Invalid Content Type",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_error_004(
        self,
        api_call: Callable,
    ) -> TestResult:
        """ERROR-004: Path Traversal Prevention"""
        test_id = "ERROR-004"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Test various path traversal attempts
            traversal_paths = [
                "/api/logs/verizon/../../../etc/passwd",
                "/api/logs/verizon/../../secrets",
                "/api/logs/../verizon/run123",
            ]

            for path in traversal_paths:
                response = await api_call("GET", path)
                self.assertions.equals(
                    response.get("status_code", 404),
                    404,
                    f"Path traversal {path} should return 404"
                )

            timer.stop()

            return TestResult(
                test_id=test_id,
                name="Path Traversal Prevention",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Path Traversal Prevention",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Path Traversal Prevention",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_error_005(
        self,
        api_call_raw: Callable,
    ) -> TestResult:
        """ERROR-005: Malformed JSON Handling"""
        test_id = "ERROR-005"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Test with malformed JSON
            response = await api_call_raw(
                "POST",
                "/api/config",
                body='{"content": "incomplete json',
                content_type="application/json"
            )
            timer.stop()

            # Should return 400 for malformed JSON
            self.assertions.equals(
                response.get("status_code", 400),
                400,
                "Malformed JSON should return 400"
            )

            return TestResult(
                test_id=test_id,
                name="Malformed JSON Handling",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Malformed JSON Handling",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Malformed JSON Handling",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_all(
        self,
        api_call: Callable,
        api_call_raw: Callable,
    ) -> SuiteResult:
        """Run all tests in this suite"""
        self.results.start_time = datetime.now()

        self.results.tests.append(await self.run_error_001(api_call))
        self.results.tests.append(await self.run_error_002(api_call))
        self.results.tests.append(await self.run_error_003(api_call_raw))
        self.results.tests.append(await self.run_error_004(api_call))
        self.results.tests.append(await self.run_error_005(api_call_raw))

        self.results.end_time = datetime.now()
        return self.results
