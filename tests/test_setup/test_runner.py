"""Tests for src/setup/runner.py orchestration."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.setup.diagnose import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    ProbeResult,
    SetupCheckpoint,
    SetupStatus,
)
from src.setup.runner import (
    _clear_checkpoint,
    _load_checkpoint,
    _save_checkpoint,
    print_diagnostic_report,
    run_setup,
)


class TestCheckpointFunctions:
    """Tests for checkpoint save/load functions."""

    def test_save_and_load_checkpoint(self, tmp_path, monkeypatch):
        """Test checkpoint round-trip."""
        checkpoint_path = tmp_path / 'data' / '.setup_checkpoint.json'
        monkeypatch.setattr('src.setup.runner.CHECKPOINT_PATH', checkpoint_path)

        checkpoint = SetupCheckpoint(
            run_id='test123',
            current_phase='probe',
            completed_checks=['check1', 'check2']
        )

        _save_checkpoint(checkpoint)
        loaded = _load_checkpoint()

        assert loaded is not None
        assert loaded.run_id == 'test123'
        assert loaded.current_phase == 'probe'
        assert loaded.completed_checks == ['check1', 'check2']

    def test_load_nonexistent_checkpoint(self, tmp_path, monkeypatch):
        """Test loading checkpoint that doesn't exist."""
        checkpoint_path = tmp_path / 'data' / '.setup_checkpoint.json'
        monkeypatch.setattr('src.setup.runner.CHECKPOINT_PATH', checkpoint_path)

        loaded = _load_checkpoint()
        assert loaded is None

    def test_clear_checkpoint(self, tmp_path, monkeypatch):
        """Test clearing checkpoint."""
        checkpoint_path = tmp_path / 'data' / '.setup_checkpoint.json'
        checkpoint_path.parent.mkdir(parents=True)
        checkpoint_path.write_text('{}')
        monkeypatch.setattr('src.setup.runner.CHECKPOINT_PATH', checkpoint_path)

        assert checkpoint_path.exists()
        _clear_checkpoint()
        assert not checkpoint_path.exists()

    def test_clear_nonexistent_checkpoint(self, tmp_path, monkeypatch):
        """Test clearing checkpoint that doesn't exist (no error)."""
        checkpoint_path = tmp_path / 'data' / '.setup_checkpoint.json'
        monkeypatch.setattr('src.setup.runner.CHECKPOINT_PATH', checkpoint_path)

        # Should not raise
        _clear_checkpoint()


class TestPrintDiagnosticReport:
    """Tests for print_diagnostic_report()."""

    def test_prints_without_error(self, capsys):
        """Test that report prints without errors."""
        probe_result = ProbeResult()
        probe_result.add_check(CheckResult(
            name="Python version",
            category=CheckCategory.CRITICAL,
            status=CheckStatus.PASS,
            details="3.11.0"
        ))
        probe_result.add_check(CheckResult(
            name="Virtual environment",
            category=CheckCategory.CORE,
            status=CheckStatus.FAIL,
            details="Missing",
            auto_fixable=True
        ))

        print_diagnostic_report(probe_result)

        captured = capsys.readouterr()
        assert "Diagnostic Report" in captured.out
        assert "[PASS]" in captured.out
        assert "[FAIL]" in captured.out
        assert "auto-fixable" in captured.out


class TestRunSetup:
    """Tests for run_setup()."""

    @patch('src.setup.runner.probe_environment')
    @patch('src.setup.runner._save_checkpoint')
    @patch('src.setup.runner._load_checkpoint', return_value=None)
    @patch('src.setup.runner._clear_checkpoint')
    def test_probe_only_mode(
        self,
        mock_clear,
        mock_load,
        mock_save,
        mock_probe,
    ):
        """Test probe-only mode returns immediately after probe."""
        mock_probe.return_value = ProbeResult()
        mock_probe.return_value.add_check(CheckResult(
            name="Test",
            category=CheckCategory.CORE,
            status=CheckStatus.PASS,
            details="OK"
        ))

        result = run_setup(probe_only=True)

        assert result.status == SetupStatus.COMPLETE
        assert result.probe_result is not None
        mock_clear.assert_called_once()

    @patch('src.setup.runner.probe_environment')
    @patch('src.setup.runner._save_checkpoint')
    @patch('src.setup.runner._load_checkpoint', return_value=None)
    def test_critical_failure_pauses(
        self,
        mock_load,
        mock_save,
        mock_probe,
    ):
        """Test that critical failures pause setup."""
        mock_probe.return_value = ProbeResult()
        mock_probe.return_value.add_check(CheckResult(
            name="Python version",
            category=CheckCategory.CRITICAL,
            status=CheckStatus.FAIL,
            details="Wrong version",
            auto_fixable=False,
            human_instructions="install_python"
        ))

        result = run_setup()

        assert result.status == SetupStatus.PAUSED
        assert "Python version" in result.pending_human_actions

    @patch('src.setup.runner.run_verification')
    @patch('src.setup.runner._save_checkpoint')
    @patch('src.setup.runner._load_checkpoint', return_value=None)
    @patch('src.setup.runner._clear_checkpoint')
    def test_verify_only_mode(
        self,
        mock_clear,
        mock_load,
        mock_save,
        mock_verify,
    ):
        """Test verify-only mode."""
        from src.setup.verify import VerificationSummary, VerificationResult

        summary = VerificationSummary()
        summary.add_result(VerificationResult(
            name="Test",
            passed=True,
            message="OK"
        ))
        mock_verify.return_value = summary

        result = run_setup(verify_only=True)

        assert result.status == SetupStatus.COMPLETE
        assert result.verification_passed is True

    @patch('src.setup.runner.run_verification')
    @patch('src.setup.runner.apply_fixes')
    @patch('src.setup.runner.probe_environment')
    @patch('src.setup.runner._save_checkpoint')
    @patch('src.setup.runner._load_checkpoint', return_value=None)
    @patch('src.setup.runner._clear_checkpoint')
    def test_full_setup_success(
        self,
        mock_clear,
        mock_load,
        mock_save,
        mock_probe,
        mock_fixes,
        mock_verify,
    ):
        """Test successful full setup flow."""
        from src.setup.verify import VerificationSummary, VerificationResult

        # Setup probe to return all passing
        probe_result = ProbeResult()
        probe_result.add_check(CheckResult(
            name="Python version",
            category=CheckCategory.CRITICAL,
            status=CheckStatus.PASS,
            details="3.11.0"
        ))
        mock_probe.return_value = probe_result

        # No fixes needed
        mock_fixes.return_value = []

        # Verification passes
        summary = VerificationSummary()
        summary.add_result(VerificationResult(
            name="Test",
            passed=True,
            message="OK"
        ))
        mock_verify.return_value = summary

        result = run_setup()

        assert result.status == SetupStatus.COMPLETE
        assert result.verification_passed is True
        mock_clear.assert_called()


class TestSetupCheckpoint:
    """Tests for SetupCheckpoint dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        checkpoint = SetupCheckpoint(
            run_id='abc123',
            current_phase='fix',
            completed_checks=['check1'],
            pending_human_actions=['action1']
        )

        data = checkpoint.to_dict()

        assert data['run_id'] == 'abc123'
        assert data['current_phase'] == 'fix'
        assert 'timestamp' in data

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'run_id': 'xyz789',
            'current_phase': 'verify',
            'completed_checks': ['a', 'b'],
            'pending_human_actions': [],
            'fix_results': [],
            'timestamp': '2024-01-01T00:00:00'
        }

        checkpoint = SetupCheckpoint.from_dict(data)

        assert checkpoint.run_id == 'xyz789'
        assert checkpoint.current_phase == 'verify'
        assert checkpoint.completed_checks == ['a', 'b']

    def test_roundtrip(self):
        """Test dict roundtrip preserves data."""
        original = SetupCheckpoint(
            run_id='test',
            current_phase='probe',
            completed_checks=['x'],
            fix_results=[{'name': 'fix1', 'status': 'fixed'}]
        )

        restored = SetupCheckpoint.from_dict(original.to_dict())

        assert restored.run_id == original.run_id
        assert restored.current_phase == original.current_phase
        assert restored.fix_results == original.fix_results
