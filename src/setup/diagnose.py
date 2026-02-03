"""Data structures for setup diagnostics and checkpoint management."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class CheckStatus(Enum):
    """Status of a setup check."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIPPED = "skipped"


class CheckCategory(Enum):
    """Category of a setup check, ordered by priority."""
    CRITICAL = "critical"      # Must pass - Python version, executable
    CORE = "core"              # Essential - venv, packages
    CONFIG = "config"          # Configuration - .env, retailers.yaml, directories
    OPTIONAL_NODE = "optional_node"      # Optional - Node.js
    OPTIONAL_DOCKER = "optional_docker"  # Optional - Docker
    CREDENTIALS = "credentials"          # Optional credentials - Oxylabs, GCS


class FixStatus(Enum):
    """Status of a fix operation."""
    FIXED = "fixed"
    ALREADY_FIXED = "already_fixed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class CheckResult:
    """Result of a single setup check."""
    name: str
    category: CheckCategory
    status: CheckStatus
    details: str
    auto_fixable: bool = False
    fix_command: Optional[str] = None
    human_instructions: Optional[str] = None

    @property
    def passed(self) -> bool:
        """Check if this result is a pass."""
        return self.status == CheckStatus.PASS

    @property
    def failed(self) -> bool:
        """Check if this result is a failure."""
        return self.status == CheckStatus.FAIL

    @property
    def is_warning(self) -> bool:
        """Check if this result is a warning."""
        return self.status == CheckStatus.WARNING


@dataclass
class ProbeResult:
    """Result of environment probing."""
    checks: List[CheckResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    platform: str = ""

    def add_check(self, check: CheckResult) -> None:
        """Add a check result."""
        self.checks.append(check)

    @property
    def critical_checks(self) -> List[CheckResult]:
        """Get all critical checks."""
        return [c for c in self.checks if c.category == CheckCategory.CRITICAL]

    @property
    def core_checks(self) -> List[CheckResult]:
        """Get all core checks."""
        return [c for c in self.checks if c.category == CheckCategory.CORE]

    @property
    def config_checks(self) -> List[CheckResult]:
        """Get all config checks."""
        return [c for c in self.checks if c.category == CheckCategory.CONFIG]

    @property
    def optional_checks(self) -> List[CheckResult]:
        """Get all optional checks (node, docker, credentials)."""
        optional_categories = {
            CheckCategory.OPTIONAL_NODE,
            CheckCategory.OPTIONAL_DOCKER,
            CheckCategory.CREDENTIALS
        }
        return [c for c in self.checks if c.category in optional_categories]

    @property
    def passed_checks(self) -> List[CheckResult]:
        """Get all passed checks."""
        return [c for c in self.checks if c.status == CheckStatus.PASS]

    @property
    def failed_checks(self) -> List[CheckResult]:
        """Get all failed checks."""
        return [c for c in self.checks if c.status == CheckStatus.FAIL]

    @property
    def warning_checks(self) -> List[CheckResult]:
        """Get all warning checks."""
        return [c for c in self.checks if c.status == CheckStatus.WARNING]

    @property
    def skipped_checks(self) -> List[CheckResult]:
        """Get all skipped checks."""
        return [c for c in self.checks if c.status == CheckStatus.SKIPPED]

    @property
    def auto_fixable_issues(self) -> List[CheckResult]:
        """Get all auto-fixable issues."""
        return [c for c in self.checks if c.status == CheckStatus.FAIL and c.auto_fixable]

    @property
    def human_required_issues(self) -> List[CheckResult]:
        """Get all issues requiring human intervention."""
        return [
            c for c in self.checks
            if c.status == CheckStatus.FAIL and not c.auto_fixable
        ]

    @property
    def has_critical_failures(self) -> bool:
        """Check if any critical checks failed."""
        return any(
            c.status == CheckStatus.FAIL and c.category == CheckCategory.CRITICAL
            for c in self.checks
        )

    @property
    def all_required_passed(self) -> bool:
        """Check if all required (critical + core + config) checks passed."""
        required_categories = {
            CheckCategory.CRITICAL,
            CheckCategory.CORE,
            CheckCategory.CONFIG
        }
        return all(
            c.status in {CheckStatus.PASS, CheckStatus.WARNING}
            for c in self.checks
            if c.category in required_categories
        )


@dataclass
class FixResult:
    """Result of applying a fix."""
    name: str
    status: FixStatus
    message: str


@dataclass
class SetupCheckpoint:
    """Checkpoint for resumable setup process."""
    run_id: str
    current_phase: str
    completed_checks: List[str] = field(default_factory=list)
    pending_human_actions: List[str] = field(default_factory=list)
    fix_results: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'run_id': self.run_id,
            'current_phase': self.current_phase,
            'completed_checks': self.completed_checks,
            'pending_human_actions': self.pending_human_actions,
            'fix_results': self.fix_results,
            'timestamp': self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SetupCheckpoint':
        """Create from dictionary."""
        return cls(
            run_id=data.get('run_id', ''),
            current_phase=data.get('current_phase', ''),
            completed_checks=data.get('completed_checks', []),
            pending_human_actions=data.get('pending_human_actions', []),
            fix_results=data.get('fix_results', []),
            timestamp=data.get('timestamp', datetime.now().isoformat())
        )


class SetupStatus(Enum):
    """Overall status of setup process."""
    COMPLETE = "complete"
    PAUSED = "paused"        # Waiting for human action
    FAILED = "failed"        # Critical failure
    IN_PROGRESS = "in_progress"


@dataclass
class SetupResult:
    """Final result of the setup process."""
    status: SetupStatus
    probe_result: Optional[ProbeResult] = None
    fix_results: List[FixResult] = field(default_factory=list)
    verification_passed: bool = False
    verification_details: Dict[str, Any] = field(default_factory=dict)
    pending_human_actions: List[str] = field(default_factory=list)
    message: str = ""
