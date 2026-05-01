"""User configuration management for real-time TER monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@dataclass
class UserConfig:
    """Typed configuration object for TER real-time monitoring."""

    realtime: dict[str, Any]
    notifications: dict[str, Any]
    ui: dict[str, Any]
    patterns: dict[str, Any]
    thresholds: dict[str, Any]
    learning: dict[str, Any]

    @classmethod
    def load(cls, config_path: Path | str | None = None) -> "UserConfig":
        """Load config from YAML file, creating defaults if missing.

        Args:
            config_path: Path to config YAML. Defaults to ~/.ter/config.yaml

        Returns:
            UserConfig instance
        """
        if config_path is None:
            config_path = Path.home() / ".ter" / "config.yaml"
        else:
            config_path = Path(config_path)

        # If YAML not available, return defaults
        if not YAML_AVAILABLE:
            return cls(**cls._get_defaults())

        if not config_path.exists():
            # Write default config
            config_path.parent.mkdir(parents=True, exist_ok=True)
            defaults = cls._get_defaults()
            with open(config_path, "w") as f:
                yaml.dump(defaults, f, default_flow_style=False, sort_keys=False)
            print(f"Created default config at {config_path}")
            return cls(**defaults)

        # Load existing config
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        # Merge with defaults to handle missing keys
        merged = cls._get_defaults()
        cls._deep_merge(merged, data)

        return cls(**merged)

    @staticmethod
    def _get_defaults() -> dict[str, Any]:
        """Return default configuration."""
        return {
            "realtime": {
                "enabled": True,
                "latency_target_ms": 100,
                "max_message_buffer_size": 10000,
            },
            "notifications": {
                "desktop_notifications": True,
                "severity_filter": ["warning", "critical"],
                "sound_enabled": False,
            },
            "ui": {
                "enabled": True,
                "refresh_rate_hz": 4,
                "color_scheme": "monokai",
            },
            "patterns": {
                "duplicate_tool_calls": {
                    "enabled": True,
                    "window_size": 5,
                    "alert_on_each": False,
                },
                "repetitive_reads": {
                    "enabled": True,
                    "min_reads": 3,
                    "alert_on_each": False,
                },
                "edit_fragmentation": {
                    "enabled": True,
                    "min_consecutive": 3,
                },
                "bash_antipatterns": {
                    "enabled": True,
                    "alert_threshold": 1,
                },
                "failed_tool_retries": {
                    "enabled": True,
                },
            },
            "thresholds": {
                "waste_percentage_warning": 5.0,
                "waste_percentage_critical": 10.0,
                # Post-hoc analysis thresholds
                "similarity_threshold": 0.40,
                "confidence_threshold": 0.75,
                "restatement_threshold": 0.85,
                "phase_weights": "0.3,0.4,0.3",
                "prompt_similarity_threshold": 0.75,
            },
            "learning": {
                "enabled": True,
                "auto_adjust_thresholds": True,
                "min_sessions_before_adjust": 5,
                "target_precision": 0.80,
                "target_recall": 0.70,
                "max_adjustment_per_session": 1,
            },
        }

    @staticmethod
    def _deep_merge(base: dict, override: dict):
        """Recursively merge override into base."""
        for key, value in override.items():
            if (
                key in base
                and isinstance(base[key], dict)
                and isinstance(value, dict)
            ):
                UserConfig._deep_merge(base[key], value)
            else:
                base[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "realtime": self.realtime,
            "notifications": self.notifications,
            "ui": self.ui,
            "patterns": self.patterns,
            "thresholds": self.thresholds,
            "learning": self.learning,
        }

    def save(self, config_path: Path | str | None = None):
        """Save configuration to YAML file.

        Args:
            config_path: Path to save config. Defaults to ~/.ter/config.yaml
        """
        if not YAML_AVAILABLE:
            raise ImportError("PyYAML is required to save configuration")

        if config_path is None:
            config_path = Path.home() / ".ter" / "config.yaml"
        else:
            config_path = Path(config_path)

        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            yaml.dump(
                self.to_dict(), f, default_flow_style=False, sort_keys=False
            )
