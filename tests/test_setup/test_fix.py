"""Tests for src/setup/fix.py auto-fix functions."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.setup.diagnose import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    FixStatus,
    ProbeResult,
)
from src.setup.fix import (
    apply_fixes,
    apply_single_fix,
    fix_directories,
    fix_env_file,
    fix_packages,
    fix_virtual_env,
)


class TestFixVirtualEnv:
    """Tests for fix_virtual_env()."""

    def test_venv_already_exists(self, tmp_path, monkeypatch):
        """Test that existing venv returns ALREADY_FIXED."""
        # Create fake venv
        venv_bin = tmp_path / 'venv' / 'bin'
        venv_bin.mkdir(parents=True)
        (venv_bin / 'python').touch()

        monkeypatch.setattr('src.setup.fix.PROJECT_ROOT', tmp_path)
        result = fix_virtual_env()
        assert result.status == FixStatus.ALREADY_FIXED

    @patch('src.setup.fix.subprocess.run')
    def test_venv_creation(self, mock_run, tmp_path, monkeypatch):
        """Test venv creation when missing."""
        mock_run.return_value = MagicMock(returncode=0)
        monkeypatch.setattr('src.setup.fix.PROJECT_ROOT', tmp_path)

        result = fix_virtual_env()
        # Note: won't actually be FIXED because venv won't exist after mock
        # Just verify subprocess was called correctly
        mock_run.assert_called_once()
        assert 'venv' in str(mock_run.call_args)


class TestFixEnvFile:
    """Tests for fix_env_file()."""

    def test_env_already_exists(self, tmp_path, monkeypatch):
        """Test that existing .env returns ALREADY_FIXED."""
        (tmp_path / '.env').write_text("KEY=value")
        monkeypatch.setattr('src.setup.fix.PROJECT_ROOT', tmp_path)

        result = fix_env_file()
        assert result.status == FixStatus.ALREADY_FIXED

    def test_env_copied_from_example(self, tmp_path, monkeypatch):
        """Test .env copied from .env.example."""
        example_content = "# Example\nKEY=value"
        (tmp_path / '.env.example').write_text(example_content)
        monkeypatch.setattr('src.setup.fix.PROJECT_ROOT', tmp_path)

        result = fix_env_file()
        assert result.status == FixStatus.FIXED

        # Verify content was copied
        env_content = (tmp_path / '.env').read_text()
        assert env_content == example_content

    def test_env_no_example(self, tmp_path, monkeypatch):
        """Test error when no .env.example exists."""
        monkeypatch.setattr('src.setup.fix.PROJECT_ROOT', tmp_path)

        result = fix_env_file()
        assert result.status == FixStatus.ERROR
        assert ".env.example not found" in result.message


class TestFixDirectories:
    """Tests for fix_directories()."""

    def test_all_dirs_exist(self, tmp_path, monkeypatch):
        """Test ALREADY_FIXED when all directories exist."""
        for dir_name in ['data', 'logs', 'runs']:
            (tmp_path / dir_name).mkdir()
        monkeypatch.setattr('src.setup.fix.PROJECT_ROOT', tmp_path)

        result = fix_directories()
        assert result.status == FixStatus.ALREADY_FIXED

    def test_creates_missing_dirs(self, tmp_path, monkeypatch):
        """Test creation of missing directories."""
        monkeypatch.setattr('src.setup.fix.PROJECT_ROOT', tmp_path)

        result = fix_directories()
        assert result.status == FixStatus.FIXED

        # Verify directories created
        assert (tmp_path / 'data').exists()
        assert (tmp_path / 'logs').exists()
        assert (tmp_path / 'runs').exists()

    def test_idempotent(self, tmp_path, monkeypatch):
        """Test that running twice doesn't cause issues."""
        monkeypatch.setattr('src.setup.fix.PROJECT_ROOT', tmp_path)

        result1 = fix_directories()
        result2 = fix_directories()

        assert result1.status == FixStatus.FIXED
        assert result2.status == FixStatus.ALREADY_FIXED


class TestApplyFixes:
    """Tests for apply_fixes()."""

    def test_no_fixable_issues(self):
        """Test with no auto-fixable issues."""
        probe_result = ProbeResult()
        probe_result.add_check(CheckResult(
            name="Test check",
            category=CheckCategory.CORE,
            status=CheckStatus.PASS,
            details="All good"
        ))

        results = apply_fixes(probe_result)
        assert len(results) == 0

    def test_dry_run_skips_fixes(self, tmp_path, monkeypatch):
        """Test that dry_run doesn't actually fix."""
        monkeypatch.setattr('src.setup.fix.PROJECT_ROOT', tmp_path)

        probe_result = ProbeResult()
        probe_result.add_check(CheckResult(
            name="Required directories",
            category=CheckCategory.CONFIG,
            status=CheckStatus.FAIL,
            details="Missing directories",
            auto_fixable=True
        ))

        results = apply_fixes(probe_result, dry_run=True)

        assert len(results) == 1
        assert results[0].status == FixStatus.SKIPPED
        assert "Would fix" in results[0].message

        # Verify directories NOT created
        assert not (tmp_path / 'data').exists()

    def test_applies_available_fixes(self, tmp_path, monkeypatch):
        """Test that available fixes are applied."""
        monkeypatch.setattr('src.setup.fix.PROJECT_ROOT', tmp_path)

        probe_result = ProbeResult()
        probe_result.add_check(CheckResult(
            name="Required directories",
            category=CheckCategory.CONFIG,
            status=CheckStatus.FAIL,
            details="Missing directories",
            auto_fixable=True
        ))

        results = apply_fixes(probe_result, confirm=False)

        assert len(results) == 1
        assert results[0].status == FixStatus.FIXED

        # Verify directories created
        assert (tmp_path / 'data').exists()


class TestApplySingleFix:
    """Tests for apply_single_fix()."""

    def test_unknown_fix_skipped(self):
        """Test that unknown check names are skipped."""
        result = apply_single_fix("Unknown check name")
        assert result.status == FixStatus.SKIPPED
        assert "No fix function" in result.message

    def test_dry_run(self, tmp_path, monkeypatch):
        """Test dry run mode."""
        monkeypatch.setattr('src.setup.fix.PROJECT_ROOT', tmp_path)

        result = apply_single_fix("Required directories", dry_run=True)
        assert result.status == FixStatus.SKIPPED
        assert not (tmp_path / 'data').exists()

    def test_applies_fix(self, tmp_path, monkeypatch):
        """Test actual fix application."""
        monkeypatch.setattr('src.setup.fix.PROJECT_ROOT', tmp_path)

        result = apply_single_fix("Required directories")
        assert result.status == FixStatus.FIXED
        assert (tmp_path / 'data').exists()
