"""Real-time pattern detectors."""

from .base import PatternDetector
from .bash_anti import BashAntipatternDetector
from .duplicate_tools import DuplicateToolCallsDetector
from .edit_frag import EditFragmentationDetector
from .failed_retry import FailedToolRetryDetector
from .repetitive_reads import RepetitiveReadsDetector

__all__ = [
    "PatternDetector",
    "DuplicateToolCallsDetector",
    "RepetitiveReadsDetector",
    "EditFragmentationDetector",
    "BashAntipatternDetector",
    "FailedToolRetryDetector",
]


def get_enabled_detectors(patterns_config: dict) -> list[PatternDetector]:
    """Create detector instances based on configuration.

    Args:
        patterns_config: Dictionary mapping pattern names to their config

    Returns:
        List of enabled detector instances
    """
    detectors = []

    detector_classes = {
        "duplicate_tool_calls": DuplicateToolCallsDetector,
        "repetitive_reads": RepetitiveReadsDetector,
        "edit_fragmentation": EditFragmentationDetector,
        "bash_antipatterns": BashAntipatternDetector,
        "failed_tool_retries": FailedToolRetryDetector,
    }

    for pattern_name, detector_class in detector_classes.items():
        pattern_config = patterns_config.get(pattern_name, {})

        # Check if enabled (default to True)
        if pattern_config.get("enabled", True):
            # Merge with default config
            full_config = detector_class({}).get_default_config()
            full_config.update(pattern_config)
            detectors.append(detector_class(full_config))

    return detectors
