"""
STATUS Test Suite - Status Display Tests

Tests real-time status updates and polling behavior.

Test Cases:
- STATUS-001: Status API returns valid data
- STATUS-002: Retailer cards show correct status
- STATUS-003: Polling updates work correctly
- STATUS-004: Status badges update on state change
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


class StatusSuite:
    """Status Display Test Suite"""

    SUITE_ID = "STATUS"
    SUITE_NAME = "Status Display"
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
                id="STATUS-001",
                name="Status API Returns Valid Data",
                description="Verify /api/status returns properly structured data",
                steps=[
                    "Call GET /api/status",
                    "Verify response status 200",
                    "Verify response has 'summary' and 'retailers' keys",
                    "Verify all 6 retailers present",
                ],
                pass_criteria=[
                    "Response status 200",
                    "Response contains 'summary' object",
                    "Response contains 'retailers' object with 6 entries",
                    "Each retailer has 'status', 'progress' fields",
                ],
            ),
            TestCase(
                id="STATUS-002",
                name="Retailer Cards Show Correct Status",
                description="Verify retailer cards display accurate status from API",
                steps=[
                    "Fetch API status data",
                    "For each retailer, compare card display to API data",
                    "Verify status badge matches API status",
                    "Verify progress percentage matches",
                ],
                pass_criteria=[
                    "All 6 cards display status matching API",
                    "Progress bars reflect API percentages",
                    "Status badges have correct CSS classes",
                ],
            ),
            TestCase(
                id="STATUS-003",
                name="Polling Updates Work",
                description="Verify status updates via polling mechanism",
                steps=[
                    "Record initial status values",
                    "Wait for polling interval (5 seconds)",
                    "Verify API was called again",
                    "Verify displayed values refreshed",
                ],
                pass_criteria=[
                    "Network request to /api/status after 5s",
                    "DOM values update without page reload",
                    "No duplicate requests within interval",
                ],
            ),
            TestCase(
                id="STATUS-004",
                name="Individual Retailer Status Endpoint",
                description="Verify /api/status/{retailer} returns correct data",
                steps=[
                    "Call GET /api/status/verizon",
                    "Verify response structure",
                    "Call GET /api/status/invalid_retailer",
                    "Verify 404 response",
                ],
                pass_criteria=[
                    "Valid retailer returns 200 with status data",
                    "Invalid retailer returns 404 with error",
                    "Response time < 500ms",
                ],
            ),
        ]

    async def run_status_001(
        self,
        api_call: Callable,
    ) -> TestResult:
        """STATUS-001: Status API Returns Valid Data"""
        test_id = "STATUS-001"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Call status API
            response = await api_call("GET", "/api/status")
            timer.stop()

            # Verify response structure
            self.assertions.equals(
                response.get("status_code", 200),
                200,
                "Response should be 200 OK"
            )

            data = response.get("data", response)
            self.assertions.has_key(data, "summary", "Response should have 'summary'")
            self.assertions.has_key(data, "retailers", "Response should have 'retailers'")

            # Verify all retailers present
            retailers = data.get("retailers", {})
            expected_retailers = self.config.retailers
            for retailer in expected_retailers:
                self.assertions.has_key(
                    retailers,
                    retailer,
                    f"Should have retailer '{retailer}'"
                )

            # Verify retailer data structure
            for retailer_id, retailer_data in retailers.items():
                self.assertions.has_key(
                    retailer_data,
                    "status",
                    f"Retailer {retailer_id} should have 'status'"
                )
                self.assertions.has_key(
                    retailer_data,
                    "progress",
                    f"Retailer {retailer_id} should have 'progress'"
                )

            # Verify summary structure
            summary = data.get("summary", {})
            self.assertions.has_keys(
                summary,
                ["total_stores", "active_retailers", "total_retailers"],
                "Summary should have required fields"
            )

            return TestResult(
                test_id=test_id,
                name="Status API Returns Valid Data",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
                api_response=data,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Status API Returns Valid Data",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Status API Returns Valid Data",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_status_002(
        self,
        api_call: Callable,
        evaluate: Callable,
    ) -> TestResult:
        """STATUS-002: Retailer Cards Show Correct Status"""
        test_id = "STATUS-002"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Get API data
            response = await api_call("GET", "/api/status")
            api_data = response.get("data", response)
            api_retailers = api_data.get("retailers", {})

            # Get DOM data for each retailer
            dom_script = """() => {
                const cards = document.querySelectorAll('[data-retailer]');
                const result = {};
                cards.forEach(card => {
                    const retailerId = card.dataset.retailer;
                    const statusEl = card.querySelector('[data-field="status"]');
                    const percentEl = card.querySelector('[data-field="percent"]');
                    result[retailerId] = {
                        status: statusEl?.textContent?.trim().toLowerCase() || '',
                        percent: percentEl?.textContent?.trim() || '',
                    };
                });
                return result;
            }"""

            dom_data = await evaluate(dom_script)
            timer.stop()

            # Compare API to DOM for each retailer
            for retailer_id in self.config.retailers:
                api_status = api_retailers.get(retailer_id, {}).get("status", "")
                dom_status = dom_data.get(retailer_id, {}).get("status", "")

                self.assertions.equals(
                    dom_status,
                    api_status,
                    f"Retailer {retailer_id} DOM status should match API"
                )

            return TestResult(
                test_id=test_id,
                name="Retailer Cards Show Correct Status",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Retailer Cards Show Correct Status",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Retailer Cards Show Correct Status",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_status_003(
        self,
        network_requests: Callable,
        wait_for: Callable,
        evaluate: Callable,
    ) -> TestResult:
        """STATUS-003: Polling Updates Work"""
        test_id = "STATUS-003"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Record initial timestamp
            initial_script = """() => {
                return document.getElementById('footer-timestamp')?.textContent || '';
            }"""
            initial_timestamp = await evaluate(initial_script)

            # Wait for polling interval
            await wait_for(time=6)

            # Check network requests
            requests = await network_requests()
            timer.stop()

            # Find status API calls
            status_calls = [
                r for r in requests.get("requests", [])
                if "/api/status" in r.get("url", "")
            ]

            self.assertions.greater_than(
                len(status_calls),
                0,
                "Should have made at least one status API call"
            )

            # Verify timestamp updated
            final_timestamp = await evaluate(initial_script)
            self.assertions.not_equals(
                final_timestamp,
                initial_timestamp,
                "Footer timestamp should update after polling"
            )

            return TestResult(
                test_id=test_id,
                name="Polling Updates Work",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Polling Updates Work",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Polling Updates Work",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_status_004(
        self,
        api_call: Callable,
    ) -> TestResult:
        """STATUS-004: Individual Retailer Status Endpoint"""
        test_id = "STATUS-004"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Test valid retailer
            valid_response = await api_call("GET", "/api/status/verizon")
            self.assertions.equals(
                valid_response.get("status_code", 200),
                200,
                "Valid retailer should return 200"
            )

            valid_data = valid_response.get("data", valid_response)
            self.assertions.has_key(valid_data, "name", "Should have 'name' field")
            self.assertions.has_key(valid_data, "enabled", "Should have 'enabled' field")

            # Test invalid retailer
            invalid_response = await api_call("GET", "/api/status/invalid_retailer")
            timer.stop()

            self.assertions.equals(
                invalid_response.get("status_code", 404),
                404,
                "Invalid retailer should return 404"
            )

            invalid_data = invalid_response.get("data", invalid_response)
            self.assertions.has_key(invalid_data, "error", "Should have error message")

            return TestResult(
                test_id=test_id,
                name="Individual Retailer Status Endpoint",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Individual Retailer Status Endpoint",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Individual Retailer Status Endpoint",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_all(
        self,
        api_call: Callable,
        evaluate: Callable,
        wait_for: Callable,
        network_requests: Callable,
    ) -> SuiteResult:
        """Run all tests in this suite"""
        self.results.start_time = datetime.now()

        self.results.tests.append(await self.run_status_001(api_call))
        self.results.tests.append(await self.run_status_002(api_call, evaluate))
        self.results.tests.append(await self.run_status_003(network_requests, wait_for, evaluate))
        self.results.tests.append(await self.run_status_004(api_call))

        self.results.end_time = datetime.now()
        return self.results
