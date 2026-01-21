"""
UAT Test Report Generator

Generates formatted test reports in multiple formats:
- Console output (text)
- JSON (machine-readable)
- HTML (human-readable)
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from .helpers import (
    UATConfig,
    SuiteResult,
    TestResult,
    TestStatus,
    Priority,
    format_duration,
    get_timestamp,
    save_json_file,
)


class ReportGenerator:
    """Generates UAT test reports"""

    def __init__(self, config: Optional[UATConfig] = None):
        self.config = config or UATConfig()
        self.suites: list[SuiteResult] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.environment: dict = {}

    def set_environment(self, env: dict):
        """Set environment information for the report"""
        self.environment = env

    def add_suite(self, suite: SuiteResult):
        """Add a suite result to the report"""
        self.suites.append(suite)

    def start(self):
        """Mark report start time"""
        self.start_time = datetime.now()

    def finish(self):
        """Mark report end time"""
        self.end_time = datetime.now()

    @property
    def total_tests(self) -> int:
        return sum(s.total for s in self.suites)

    @property
    def passed_tests(self) -> int:
        return sum(s.passed for s in self.suites)

    @property
    def failed_tests(self) -> int:
        return sum(s.failed for s in self.suites)

    @property
    def skipped_tests(self) -> int:
        return sum(s.skipped for s in self.suites)

    @property
    def pass_rate(self) -> float:
        if self.total_tests == 0:
            return 0
        return (self.passed_tests / self.total_tests) * 100

    @property
    def duration_ms(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return sum(s.duration_ms for s in self.suites)

    def _get_status_bar(self, passed: int, total: int, width: int = 20) -> str:
        """Generate a text-based status bar"""
        if total == 0:
            return "[" + "-" * width + "]"
        filled = int((passed / total) * width)
        return "[" + "=" * filled + " " * (width - filled) + "]"

    def _get_status_indicator(self, suite: SuiteResult) -> str:
        """Get status indicator for suite"""
        if suite.failed > 0:
            return "FAIL"
        elif suite.skipped > 0:
            return "SKIP"
        else:
            return "PASS"

    def generate_console_report(self) -> str:
        """Generate console-formatted text report"""
        lines = []
        border = "=" * 60

        lines.append("")
        lines.append(border)
        lines.append("UAT EXECUTION REPORT")
        lines.append(border)
        lines.append("")

        # Metadata
        lines.append(f"Date: {self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else 'N/A'}")
        lines.append(f"Environment: {self.environment.get('base_url', 'N/A')}")
        lines.append(f"Duration: {format_duration(self.duration_ms)}")
        lines.append("")

        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 60)
        lines.append(f"Total: {self.total_tests} | Pass: {self.passed_tests} | Fail: {self.failed_tests} | Skip: {self.skipped_tests}")
        lines.append(f"Pass Rate: {self.pass_rate:.1f}%")
        lines.append("")

        # By Suite
        lines.append("BY SUITE")
        lines.append("-" * 60)

        # Sort suites by priority
        priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
        sorted_suites = sorted(self.suites, key=lambda s: priority_order.get(s.priority, 99))

        for suite in sorted_suites:
            status_bar = self._get_status_bar(suite.passed, suite.total)
            status = self._get_status_indicator(suite)
            priority_str = f"[{suite.priority.value.upper()}]"
            lines.append(f"{suite.suite_id:10} {priority_str:10} {suite.passed}/{suite.total}  {status_bar}  {status}")

        # Failures
        failures = []
        for suite in self.suites:
            for test in suite.tests:
                if test.status == TestStatus.FAILED:
                    failures.append((suite.suite_id, test))

        if failures:
            lines.append("")
            lines.append("FAILURES")
            lines.append("-" * 60)
            for suite_id, test in failures:
                lines.append(f"")
                lines.append(f"{test.test_id}: {test.name}")
                lines.append(f"  Error: {test.error_message or 'Unknown error'}")
                if test.screenshot_path:
                    lines.append(f"  Evidence: {test.screenshot_path}")

        # Performance Summary
        perf_suite = next((s for s in self.suites if s.suite_id == "PERF"), None)
        if perf_suite:
            lines.append("")
            lines.append("PERFORMANCE")
            lines.append("-" * 60)
            for test in perf_suite.tests:
                status = "PASS" if test.status == TestStatus.PASSED else "FAIL"
                lines.append(f"  {test.name}: {status} ({format_duration(test.duration_ms)})")

        # Recommendations
        recommendations = self._generate_recommendations()
        if recommendations:
            lines.append("")
            lines.append("RECOMMENDATIONS")
            lines.append("-" * 60)
            for rec in recommendations:
                lines.append(f"  - {rec}")

        lines.append("")
        lines.append(border)
        lines.append("")

        return "\n".join(lines)

    def _generate_recommendations(self) -> list[str]:
        """Generate actionable recommendations based on failures"""
        recommendations = []

        for suite in self.suites:
            for test in suite.tests:
                if test.status != TestStatus.FAILED:
                    continue

                # Generate recommendations based on test failures
                if "INIT" in test.test_id:
                    recommendations.append(
                        "Check that Flask server is running on port 5001"
                    )
                elif "API" in test.test_id:
                    recommendations.append(
                        f"Review API endpoint implementation for {test.name}"
                    )
                elif "CONTROL" in test.test_id:
                    recommendations.append(
                        "Verify scraper manager is properly initialized"
                    )
                elif "CONFIG" in test.test_id:
                    recommendations.append(
                        "Check config file permissions and YAML validation"
                    )
                elif "PERF" in test.test_id:
                    recommendations.append(
                        "Investigate performance bottlenecks in dashboard"
                    )

        return list(set(recommendations))[:5]  # Return unique, max 5

    def generate_json_report(self) -> dict:
        """Generate JSON-formatted report"""
        return {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration_ms": self.duration_ms,
                "environment": self.environment,
            },
            "summary": {
                "total": self.total_tests,
                "passed": self.passed_tests,
                "failed": self.failed_tests,
                "skipped": self.skipped_tests,
                "pass_rate": self.pass_rate,
            },
            "suites": [s.to_dict() for s in self.suites],
            "recommendations": self._generate_recommendations(),
        }

    def generate_html_report(self) -> str:
        """Generate HTML-formatted report"""
        pass_color = "#22c55e"
        fail_color = "#ef4444"
        skip_color = "#eab308"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UAT Report - {self.start_time.strftime('%Y-%m-%d') if self.start_time else 'N/A'}</title>
    <style>
        :root {{
            --bg: #1a1a2e;
            --card: #16213e;
            --border: #0f3460;
            --text: #eaeaea;
            --muted: #888;
            --pass: {pass_color};
            --fail: {fail_color};
            --skip: {skip_color};
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ margin-bottom: 1rem; }}
        h2 {{ margin: 2rem 0 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}

        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .stat {{
            background: var(--card);
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-value {{ font-size: 2.5rem; font-weight: bold; }}
        .stat-label {{ color: var(--muted); font-size: 0.875rem; text-transform: uppercase; }}

        .progress-bar {{
            height: 8px;
            background: var(--border);
            border-radius: 4px;
            overflow: hidden;
            margin: 1rem 0;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--pass), var(--pass));
            transition: width 0.3s;
        }}

        .suites {{ display: flex; flex-direction: column; gap: 1rem; }}
        .suite {{
            background: var(--card);
            border-radius: 8px;
            padding: 1rem 1.5rem;
            border-left: 4px solid var(--border);
        }}
        .suite.pass {{ border-left-color: var(--pass); }}
        .suite.fail {{ border-left-color: var(--fail); }}
        .suite-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }}
        .suite-name {{ font-weight: 600; }}
        .suite-stats {{ color: var(--muted); font-size: 0.875rem; }}
        .priority {{
            display: inline-block;
            padding: 0.125rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            text-transform: uppercase;
            background: var(--border);
        }}
        .priority.critical {{ background: var(--fail); color: white; }}
        .priority.high {{ background: #f97316; color: white; }}

        .failures {{ margin-top: 2rem; }}
        .failure {{
            background: var(--card);
            border-left: 4px solid var(--fail);
            padding: 1rem 1.5rem;
            margin-bottom: 1rem;
            border-radius: 8px;
        }}
        .failure-id {{ font-weight: 600; color: var(--fail); }}
        .failure-message {{ color: var(--muted); margin-top: 0.5rem; font-family: monospace; }}

        .meta {{
            color: var(--muted);
            font-size: 0.875rem;
            margin-top: 2rem;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>UAT Execution Report</h1>
        <p class="meta" style="text-align: left; margin-top: 0;">
            {self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else 'N/A'} |
            {self.environment.get('base_url', 'N/A')} |
            Duration: {format_duration(self.duration_ms)}
        </p>

        <div class="summary">
            <div class="stat">
                <div class="stat-value">{self.total_tests}</div>
                <div class="stat-label">Total Tests</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: var(--pass)">{self.passed_tests}</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: var(--fail)">{self.failed_tests}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: var(--skip)">{self.skipped_tests}</div>
                <div class="stat-label">Skipped</div>
            </div>
            <div class="stat">
                <div class="stat-value">{self.pass_rate:.1f}%</div>
                <div class="stat-label">Pass Rate</div>
            </div>
        </div>

        <div class="progress-bar">
            <div class="progress-fill" style="width: {self.pass_rate}%"></div>
        </div>

        <h2>Test Suites</h2>
        <div class="suites">
"""

        # Sort suites by priority
        priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
        sorted_suites = sorted(self.suites, key=lambda s: priority_order.get(s.priority, 99))

        for suite in sorted_suites:
            status_class = "fail" if suite.failed > 0 else "pass"
            priority_class = suite.priority.value.lower()
            html += f"""
            <div class="suite {status_class}">
                <div class="suite-header">
                    <span class="suite-name">{suite.suite_id} - {suite.name}</span>
                    <span class="priority {priority_class}">{suite.priority.value}</span>
                </div>
                <div class="suite-stats">
                    {suite.passed}/{suite.total} passed | {format_duration(suite.duration_ms)}
                </div>
            </div>
"""

        # Failures section
        failures = []
        for suite in self.suites:
            for test in suite.tests:
                if test.status == TestStatus.FAILED:
                    failures.append(test)

        if failures:
            html += """
        <h2>Failures</h2>
        <div class="failures">
"""
            for test in failures:
                html += f"""
            <div class="failure">
                <div class="failure-id">{test.test_id}: {test.name}</div>
                <div class="failure-message">{test.error_message or 'Unknown error'}</div>
            </div>
"""
            html += """
        </div>
"""

        html += f"""
        <p class="meta">
            Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
</body>
</html>
"""
        return html

    def save(self, output_dir: Optional[str] = None) -> dict[str, str]:
        """Save reports to files and return paths"""
        if output_dir is None:
            output_dir = self.config.reporting["output_dir"]

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = get_timestamp()
        paths = {}

        # Console report
        console_path = output_path / f"report_{timestamp}.txt"
        with open(console_path, "w") as f:
            f.write(self.generate_console_report())
        paths["console"] = str(console_path)

        # JSON report
        json_path = output_path / f"report_{timestamp}.json"
        save_json_file(str(json_path), self.generate_json_report())
        paths["json"] = str(json_path)

        # HTML report
        html_path = output_path / f"report_{timestamp}.html"
        with open(html_path, "w") as f:
            f.write(self.generate_html_report())
        paths["html"] = str(html_path)

        return paths


def print_report(report: ReportGenerator):
    """Print report to console"""
    print(report.generate_console_report())
