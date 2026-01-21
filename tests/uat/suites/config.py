"""
CONFIG Test Suite - Configuration Management Tests

Tests configuration viewing, editing, and saving functionality.

Test Cases:
- CONFIG-001: Get Configuration
- CONFIG-002: Open Config Modal
- CONFIG-003: Save Valid Configuration
- CONFIG-004: Invalid YAML Rejected
- CONFIG-005: Backup Created on Save
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
    VALID_TEST_CONFIG,
    INVALID_YAML_SYNTAX,
    INVALID_CONFIG_MISSING_RETAILERS,
)


@dataclass
class TestCase:
    """Test case definition"""
    id: str
    name: str
    description: str
    steps: list[str]
    pass_criteria: list[str]


class ConfigSuite:
    """Configuration Management Test Suite"""

    SUITE_ID = "CONFIG"
    SUITE_NAME = "Configuration"
    PRIORITY = Priority.HIGH

    def __init__(self, config: Optional[UATConfig] = None):
        self.config = config or UATConfig()
        self.assertions = Assertions()
        self.results = SuiteResult(
            suite_id=self.SUITE_ID,
            name=self.SUITE_NAME,
            priority=self.PRIORITY,
        )
        self._original_config = None

    def get_test_cases(self) -> list[TestCase]:
        """Return all test cases in this suite"""
        return [
            TestCase(
                id="CONFIG-001",
                name="Get Configuration",
                description="Verify GET /api/config returns YAML content",
                steps=[
                    "Call GET /api/config",
                    "Verify response status 200",
                    "Verify content contains YAML structure",
                ],
                pass_criteria=[
                    "Response status 200",
                    "Response has 'content' field",
                    "Content contains 'retailers:' key",
                ],
            ),
            TestCase(
                id="CONFIG-002",
                name="Open Config Modal",
                description="Verify config modal opens and loads data",
                steps=[
                    "Click Config button in header",
                    "Wait for modal to appear",
                    "Verify textarea populated with config",
                ],
                pass_criteria=[
                    "Modal overlay becomes visible",
                    "Textarea contains YAML content",
                    "Close button present",
                ],
            ),
            TestCase(
                id="CONFIG-003",
                name="Save Valid Configuration",
                description="Verify valid YAML can be saved",
                steps=[
                    "Open config modal",
                    "Modify YAML content",
                    "Click Save button",
                    "Verify success response",
                ],
                pass_criteria=[
                    "POST /api/config returns 200",
                    "Success message shown",
                    "Backup path in response",
                ],
            ),
            TestCase(
                id="CONFIG-004",
                name="Invalid YAML Rejected",
                description="Verify invalid YAML syntax is rejected",
                steps=[
                    "POST /api/config with invalid YAML",
                    "Verify 400 response",
                    "Verify error message explains issue",
                ],
                pass_criteria=[
                    "Response status 400",
                    "Error message mentions YAML syntax",
                    "Original config unchanged",
                ],
            ),
            TestCase(
                id="CONFIG-005",
                name="Validation Errors Reported",
                description="Verify config validation catches missing fields",
                steps=[
                    "POST /api/config missing 'retailers' key",
                    "Verify 400 response",
                    "Verify validation error details",
                ],
                pass_criteria=[
                    "Response status 400",
                    "Error mentions validation failed",
                    "Details list missing fields",
                ],
            ),
        ]

    async def run_config_001(
        self,
        api_call: Callable,
    ) -> TestResult:
        """CONFIG-001: Get Configuration"""
        test_id = "CONFIG-001"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            response = await api_call("GET", "/api/config")
            timer.stop()

            self.assertions.equals(
                response.get("status_code", 200),
                200,
                "Response should be 200 OK"
            )

            data = response.get("data", response)
            self.assertions.has_key(data, "content", "Response should have 'content'")
            self.assertions.has_key(data, "path", "Response should have 'path'")

            content = data.get("content", "")
            self.assertions.contains(
                content,
                "retailers:",
                "Config should contain 'retailers:' key"
            )

            # Store original config for later tests
            self._original_config = content

            return TestResult(
                test_id=test_id,
                name="Get Configuration",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Get Configuration",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Get Configuration",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_config_002(
        self,
        snapshot: Callable,
        click: Callable,
        wait_for: Callable,
        evaluate: Callable,
    ) -> TestResult:
        """CONFIG-002: Open Config Modal"""
        test_id = "CONFIG-002"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Get snapshot and find config button
            snap = await snapshot()
            parser = SnapshotParser(snap)

            # Click config button
            config_btn_ref = parser.find_button("Config")
            if config_btn_ref:
                await click("Config button", config_btn_ref)

            # Wait for modal to appear
            await wait_for(time=0.5)

            # Check modal is visible
            modal_script = """() => {
                const modal = document.getElementById('config-modal');
                const editor = document.getElementById('config-editor');
                return {
                    modalVisible: modal?.classList.contains('active') ||
                                  getComputedStyle(modal).display !== 'none',
                    editorContent: editor?.value || '',
                    hasCloseBtn: !!document.getElementById('config-modal-close'),
                };
            }"""

            modal_state = await evaluate(modal_script)
            timer.stop()

            self.assertions.true(
                modal_state["modalVisible"],
                "Config modal should be visible"
            )

            self.assertions.true(
                len(modal_state["editorContent"]) > 0,
                "Config editor should have content"
            )

            self.assertions.true(
                modal_state["hasCloseBtn"],
                "Modal should have close button"
            )

            # Close modal for next tests
            close_script = """() => {
                const closeBtn = document.getElementById('config-modal-close');
                if (closeBtn) closeBtn.click();
            }"""
            await evaluate(close_script)

            return TestResult(
                test_id=test_id,
                name="Open Config Modal",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Open Config Modal",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Open Config Modal",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_config_003(
        self,
        api_call: Callable,
    ) -> TestResult:
        """CONFIG-003: Save Valid Configuration"""
        test_id = "CONFIG-003"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            # Use the valid test config
            response = await api_call(
                "POST",
                "/api/config",
                {"content": VALID_TEST_CONFIG}
            )
            timer.stop()

            self.assertions.equals(
                response.get("status_code", 200),
                200,
                "Valid config should return 200"
            )

            data = response.get("data", response)
            self.assertions.has_key(data, "message", "Should have success message")
            self.assertions.has_key(data, "backup", "Should have backup path")

            self.assertions.contains(
                data.get("message", ""),
                "success",
                "Message should indicate success"
            )

            return TestResult(
                test_id=test_id,
                name="Save Valid Configuration",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Save Valid Configuration",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Save Valid Configuration",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_config_004(
        self,
        api_call: Callable,
    ) -> TestResult:
        """CONFIG-004: Invalid YAML Rejected"""
        test_id = "CONFIG-004"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            response = await api_call(
                "POST",
                "/api/config",
                {"content": INVALID_YAML_SYNTAX}
            )
            timer.stop()

            self.assertions.equals(
                response.get("status_code", 400),
                400,
                "Invalid YAML should return 400"
            )

            data = response.get("data", response)
            self.assertions.has_key(data, "error", "Should have error message")

            error_msg = data.get("error", "").lower()
            self.assertions.true(
                "yaml" in error_msg or "syntax" in error_msg,
                "Error should mention YAML syntax issue"
            )

            return TestResult(
                test_id=test_id,
                name="Invalid YAML Rejected",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Invalid YAML Rejected",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Invalid YAML Rejected",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_config_005(
        self,
        api_call: Callable,
    ) -> TestResult:
        """CONFIG-005: Validation Errors Reported"""
        test_id = "CONFIG-005"
        self.assertions.reset()
        timer = Timer()

        try:
            timer.start()

            response = await api_call(
                "POST",
                "/api/config",
                {"content": INVALID_CONFIG_MISSING_RETAILERS}
            )
            timer.stop()

            self.assertions.equals(
                response.get("status_code", 400),
                400,
                "Missing retailers key should return 400"
            )

            data = response.get("data", response)
            self.assertions.has_key(data, "error", "Should have error message")

            error_msg = data.get("error", "").lower()
            self.assertions.true(
                "validation" in error_msg,
                "Error should mention validation"
            )

            # Check for details if present
            if "details" in data:
                self.assertions.true(
                    len(data["details"]) > 0,
                    "Should have validation error details"
                )

            return TestResult(
                test_id=test_id,
                name="Validation Errors Reported",
                status=TestStatus.PASSED,
                duration_ms=timer.elapsed_ms,
                assertions=self.assertions.results,
            )

        except AssertionError as e:
            return TestResult(
                test_id=test_id,
                name="Validation Errors Reported",
                status=TestStatus.FAILED,
                duration_ms=timer.elapsed_ms,
                error_message=str(e),
                assertions=self.assertions.results,
            )
        except Exception as e:
            return TestResult(
                test_id=test_id,
                name="Validation Errors Reported",
                status=TestStatus.ERROR,
                duration_ms=timer.elapsed_ms,
                error_message=f"Unexpected error: {str(e)}",
            )

    async def run_all(
        self,
        api_call: Callable,
        snapshot: Callable,
        click: Callable,
        wait_for: Callable,
        evaluate: Callable,
    ) -> SuiteResult:
        """Run all tests in this suite"""
        self.results.start_time = datetime.now()

        self.results.tests.append(await self.run_config_001(api_call))
        self.results.tests.append(
            await self.run_config_002(snapshot, click, wait_for, evaluate)
        )
        self.results.tests.append(await self.run_config_003(api_call))
        self.results.tests.append(await self.run_config_004(api_call))
        self.results.tests.append(await self.run_config_005(api_call))

        self.results.end_time = datetime.now()
        return self.results
