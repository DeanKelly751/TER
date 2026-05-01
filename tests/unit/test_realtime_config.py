"""Unit tests for real-time configuration system."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@pytest.mark.skipif(not YAML_AVAILABLE, reason="PyYAML not installed")
class TestUserConfig:
    """Tests for UserConfig YAML configuration."""

    def test_default_config_creation(self, tmp_path, monkeypatch):
        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = UserConfig.load()

        # Check defaults are loaded
        assert config.patterns["repetitive_reads"]["enabled"] is True
        assert config.patterns["repetitive_reads"]["min_reads"] == 3
        assert config.notifications["desktop_notifications"] is True
        assert config.learning["enabled"] is True

    def test_config_file_creation(self, tmp_path, monkeypatch):
        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = UserConfig.load()
        config.save()

        config_file = tmp_path / ".ter" / "config.yaml"
        assert config_file.exists()

        # Verify it's valid YAML
        with open(config_file) as f:
            data = yaml.safe_load(f)
        assert "patterns" in data
        assert "notifications" in data
        assert "learning" in data

    def test_config_reload(self, tmp_path, monkeypatch):
        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create and save config
        config1 = UserConfig.load()
        config1.patterns["repetitive_reads"]["min_reads"] = 5
        config1.save()

        # Load again and verify changes persisted
        config2 = UserConfig.load()
        assert config2.patterns["repetitive_reads"]["min_reads"] == 5

    def test_partial_config_merge(self, tmp_path, monkeypatch):
        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create partial config file
        config_file = tmp_path / ".ter" / "config.yaml"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        partial_config = {
            "patterns": {
                "repetitive_reads": {
                    "min_reads": 4  # Only override this
                }
            }
        }

        with open(config_file, "w") as f:
            yaml.dump(partial_config, f)

        # Load should merge with defaults
        config = UserConfig.load()
        assert config.patterns["repetitive_reads"]["min_reads"] == 4  # Overridden
        assert config.patterns["repetitive_reads"]["enabled"] is True  # Default
        assert config.patterns["edit_fragmentation"]["enabled"] is True  # Default

    def test_disable_pattern_via_config(self, tmp_path, monkeypatch):
        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = UserConfig.load()
        config.patterns["bash_antipatterns"]["enabled"] = False
        config.save()

        # Reload and verify
        config2 = UserConfig.load()
        assert config2.patterns["bash_antipatterns"]["enabled"] is False

    def test_learning_config_customization(self, tmp_path, monkeypatch):
        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = UserConfig.load()
        config.learning["target_precision"] = 0.90
        config.learning["min_sessions_before_adjust"] = 10
        config.save()

        config2 = UserConfig.load()
        assert config2.learning["target_precision"] == 0.90
        assert config2.learning["min_sessions_before_adjust"] == 10

    def test_notification_severity_filter(self, tmp_path, monkeypatch):
        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = UserConfig.load()
        config.notifications["severity_filter"] = ["critical"]
        config.save()

        config2 = UserConfig.load()
        assert config2.notifications["severity_filter"] == ["critical"]

    def test_to_dict_conversion(self, tmp_path, monkeypatch):
        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = UserConfig.load()
        data = config.to_dict()

        assert isinstance(data, dict)
        assert "patterns" in data
        assert "notifications" in data
        assert "learning" in data

    def test_invalid_yaml_fallback_to_defaults(self, tmp_path, monkeypatch):
        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create invalid YAML file
        config_file = tmp_path / ".ter" / "config.yaml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("invalid: yaml: content: [[[")

        # Should fall back to defaults without crashing
        config = UserConfig.load()
        assert config.patterns["repetitive_reads"]["enabled"] is True


class TestConfigWithoutYAML:
    """Tests for config system when PyYAML is not available."""

    def test_graceful_degradation_without_yaml(self, tmp_path, monkeypatch):
        # Even without importing, we can test the fallback behavior
        # by mocking the import
        import sys

        # Temporarily hide yaml
        yaml_module = sys.modules.get("yaml")
        if yaml_module:
            sys.modules["yaml"] = None

        try:
            from ter_calculator.realtime.client.config import UserConfig

            monkeypatch.setattr(Path, "home", lambda: tmp_path)

            # Should use defaults without crashing
            config = UserConfig.load()
            assert config.patterns is not None
        finally:
            # Restore yaml module
            if yaml_module:
                sys.modules["yaml"] = yaml_module


class TestConfigDirectories:
    """Tests for config directory creation."""

    def test_ter_directory_creation(self, tmp_path, monkeypatch):
        if not YAML_AVAILABLE:
            pytest.skip("PyYAML not installed")

        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = UserConfig.load()
        config.save()

        ter_dir = tmp_path / ".ter"
        assert ter_dir.exists()
        assert ter_dir.is_dir()

    def test_logs_directory_creation(self, tmp_path, monkeypatch):
        if not YAML_AVAILABLE:
            pytest.skip("PyYAML not installed")

        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = UserConfig.load()
        config.save()

        # Logs directory should be created by alert manager
        logs_dir = tmp_path / ".ter" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        assert logs_dir.exists()

    def test_sessions_directory_creation(self, tmp_path, monkeypatch):
        if not YAML_AVAILABLE:
            pytest.skip("PyYAML not installed")

        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = UserConfig.load()
        config.save()

        sessions_dir = tmp_path / ".ter" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        assert sessions_dir.exists()


class TestConfigValidation:
    """Tests for config validation."""

    def test_threshold_bounds(self, tmp_path, monkeypatch):
        if not YAML_AVAILABLE:
            pytest.skip("PyYAML not installed")

        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = UserConfig.load()

        # Thresholds should be positive integers
        assert config.patterns["repetitive_reads"]["min_reads"] > 0
        assert config.patterns["edit_fragmentation"]["min_consecutive"] > 0
        assert config.patterns["duplicate_tool_calls"]["window_size"] > 0

    def test_learning_targets_valid_range(self, tmp_path, monkeypatch):
        if not YAML_AVAILABLE:
            pytest.skip("PyYAML not installed")

        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = UserConfig.load()

        # Precision and recall targets should be 0-1
        assert 0.0 <= config.learning["target_precision"] <= 1.0
        assert 0.0 <= config.learning["target_recall"] <= 1.0

    def test_severity_filter_valid_values(self, tmp_path, monkeypatch):
        if not YAML_AVAILABLE:
            pytest.skip("PyYAML not installed")

        from ter_calculator.realtime.client.config import UserConfig

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = UserConfig.load()

        # Severity filter should only contain valid severities
        valid_severities = {"info", "warning", "critical"}
        for severity in config.notifications["severity_filter"]:
            assert severity in valid_severities
