"""Tests for src/setup/probe.py environment probing."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.setup.diagnose import CheckCategory, CheckStatus
from src.setup.probe import (
    check_directories,
    check_docker,
    check_env_file,
    check_nodejs,
    check_packages,
    check_python_executable,
    check_python_version,
    check_retailers_yaml,
    check_virtual_env,
    probe_environment,
)


class TestCheckPythonVersion:
    """Tests for check_python_version()."""

    def test_valid_python_version(self):
        """Test that current Python version passes (assuming 3.8-3.11)."""
        result = check_python_version()
        # Since we're running tests, Python version should be valid
        assert result.category == CheckCategory.CRITICAL
        # Check passes on 3.8-3.11, fails otherwise
        if (3, 8) <= sys.version_info[:2] <= (3, 11):
            assert result.status == CheckStatus.PASS
        else:
            assert result.status == CheckStatus.FAIL

    @patch('src.setup.probe.sys.version_info', (3, 7, 0))
    def test_python_37_fails(self):
        """Test that Python 3.7 fails the version check."""
        result = check_python_version()
        assert result.status == CheckStatus.FAIL
        assert "3.7" in result.details

    @patch('src.setup.probe.sys.version_info', (3, 12, 0))
    def test_python_312_fails(self):
        """Test that Python 3.12 fails the version check."""
        result = check_python_version()
        assert result.status == CheckStatus.FAIL
        assert "3.12" in result.details


class TestCheckPythonExecutable:
    """Tests for check_python_executable()."""

    def test_python3_found(self):
        """Test that python3 executable is found."""
        result = check_python_executable()
        assert result.category == CheckCategory.CRITICAL
        # Should pass on any system with Python 3 installed
        assert result.status == CheckStatus.PASS
        assert "Found at" in result.details

    @patch('src.setup.probe.shutil.which', return_value=None)
    def test_python3_not_found(self, mock_which):
        """Test behavior when python3 is not in PATH."""
        result = check_python_executable()
        assert result.status == CheckStatus.FAIL
        assert "not found" in result.details


class TestCheckVirtualEnv:
    """Tests for check_virtual_env()."""

    def test_venv_exists(self, tmp_path, monkeypatch):
        """Test detection of existing virtual environment."""
        # Create fake venv structure
        venv_bin = tmp_path / 'venv' / 'bin'
        venv_bin.mkdir(parents=True)
        (venv_bin / 'python').touch()

        monkeypatch.setattr('src.setup.probe.PROJECT_ROOT', tmp_path)
        result = check_virtual_env()
        assert result.status == CheckStatus.PASS

    def test_venv_missing(self, tmp_path, monkeypatch):
        """Test detection of missing virtual environment."""
        monkeypatch.setattr('src.setup.probe.PROJECT_ROOT', tmp_path)
        result = check_virtual_env()
        assert result.status == CheckStatus.FAIL
        assert result.auto_fixable is True
        assert "venv" in result.fix_command


class TestCheckEnvFile:
    """Tests for check_env_file()."""

    def test_env_exists(self, tmp_path, monkeypatch):
        """Test detection of existing .env file."""
        (tmp_path / '.env').touch()
        monkeypatch.setattr('src.setup.probe.PROJECT_ROOT', tmp_path)
        result = check_env_file()
        assert result.status == CheckStatus.PASS

    def test_env_missing_with_example(self, tmp_path, monkeypatch):
        """Test .env missing but .env.example exists."""
        (tmp_path / '.env.example').touch()
        monkeypatch.setattr('src.setup.probe.PROJECT_ROOT', tmp_path)
        result = check_env_file()
        assert result.status == CheckStatus.FAIL
        assert result.auto_fixable is True
        assert "cp" in result.fix_command

    def test_env_missing_no_example(self, tmp_path, monkeypatch):
        """Test .env missing and no .env.example."""
        monkeypatch.setattr('src.setup.probe.PROJECT_ROOT', tmp_path)
        result = check_env_file()
        assert result.status == CheckStatus.WARNING
        assert result.auto_fixable is False


class TestCheckRetailersYaml:
    """Tests for check_retailers_yaml()."""

    def test_valid_yaml(self, tmp_path, monkeypatch):
        """Test valid retailers.yaml."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        (config_dir / 'retailers.yaml').write_text("""
retailers:
  verizon:
    enabled: true
""")
        monkeypatch.setattr('src.setup.probe.PROJECT_ROOT', tmp_path)
        result = check_retailers_yaml()
        assert result.status == CheckStatus.PASS

    def test_missing_yaml(self, tmp_path, monkeypatch):
        """Test missing retailers.yaml."""
        monkeypatch.setattr('src.setup.probe.PROJECT_ROOT', tmp_path)
        result = check_retailers_yaml()
        assert result.status == CheckStatus.FAIL
        assert "not found" in result.details

    def test_invalid_yaml(self, tmp_path, monkeypatch):
        """Test invalid YAML syntax."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        (config_dir / 'retailers.yaml').write_text("invalid: yaml: syntax:")
        monkeypatch.setattr('src.setup.probe.PROJECT_ROOT', tmp_path)
        result = check_retailers_yaml()
        assert result.status == CheckStatus.FAIL
        assert "Invalid YAML" in result.details

    def test_missing_retailers_section(self, tmp_path, monkeypatch):
        """Test YAML without retailers section."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        (config_dir / 'retailers.yaml').write_text("other_key: value")
        monkeypatch.setattr('src.setup.probe.PROJECT_ROOT', tmp_path)
        result = check_retailers_yaml()
        assert result.status == CheckStatus.FAIL
        assert "Missing 'retailers'" in result.details


class TestCheckDirectories:
    """Tests for check_directories()."""

    def test_all_dirs_exist(self, tmp_path, monkeypatch):
        """Test when all required directories exist."""
        for dir_name in ['data', 'logs', 'runs']:
            (tmp_path / dir_name).mkdir()
        monkeypatch.setattr('src.setup.probe.PROJECT_ROOT', tmp_path)
        result = check_directories()
        assert result.status == CheckStatus.PASS

    def test_some_dirs_missing(self, tmp_path, monkeypatch):
        """Test when some directories are missing."""
        (tmp_path / 'data').mkdir()
        monkeypatch.setattr('src.setup.probe.PROJECT_ROOT', tmp_path)
        result = check_directories()
        assert result.status == CheckStatus.FAIL
        assert result.auto_fixable is True
        assert "logs" in result.details or "runs" in result.details


class TestCheckNodejs:
    """Tests for check_nodejs()."""

    @patch('src.setup.probe.shutil.which', return_value='/usr/bin/node')
    @patch('src.setup.probe.subprocess.run')
    def test_nodejs_installed(self, mock_run, mock_which):
        """Test Node.js detection when installed."""
        mock_run.return_value = MagicMock(
            stdout='v18.17.0\n',
            returncode=0
        )
        result = check_nodejs()
        assert result.status == CheckStatus.PASS
        assert result.category == CheckCategory.OPTIONAL_NODE

    @patch('src.setup.probe.shutil.which', return_value=None)
    def test_nodejs_not_installed(self, mock_which):
        """Test Node.js detection when not installed."""
        result = check_nodejs()
        assert result.status == CheckStatus.SKIPPED
        assert "Not installed" in result.details


class TestCheckDocker:
    """Tests for check_docker()."""

    @patch('src.setup.probe.shutil.which', return_value='/usr/bin/docker')
    @patch('src.setup.probe.subprocess.run')
    def test_docker_installed(self, mock_run, mock_which):
        """Test Docker detection when installed."""
        mock_run.return_value = MagicMock(
            stdout='Docker version 24.0.0\n',
            returncode=0
        )
        result = check_docker()
        assert result.status == CheckStatus.PASS
        assert result.category == CheckCategory.OPTIONAL_DOCKER

    @patch('src.setup.probe.shutil.which', return_value=None)
    def test_docker_not_installed(self, mock_which):
        """Test Docker detection when not installed."""
        result = check_docker()
        assert result.status == CheckStatus.SKIPPED
        assert "Not installed" in result.details


class TestProbeEnvironment:
    """Tests for probe_environment()."""

    def test_probe_returns_result(self):
        """Test that probe_environment returns a ProbeResult."""
        result = probe_environment()
        assert hasattr(result, 'checks')
        assert hasattr(result, 'platform')
        assert len(result.checks) > 0

    def test_probe_has_critical_checks(self):
        """Test that probe includes critical checks."""
        result = probe_environment()
        critical = result.critical_checks
        assert len(critical) >= 2  # Python version and executable

    def test_probe_properties_work(self):
        """Test that ProbeResult properties work correctly."""
        result = probe_environment()

        # These properties should not raise
        _ = result.passed_checks
        _ = result.failed_checks
        _ = result.warning_checks
        _ = result.skipped_checks
        _ = result.auto_fixable_issues
        _ = result.human_required_issues
        _ = result.has_critical_failures
        _ = result.all_required_passed
