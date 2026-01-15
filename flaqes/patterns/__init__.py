"""
Pattern matching module for database design pattern detection.

This module provides pattern detection for common database design patterns
like SCD Type 2, soft deletes, polymorphic associations, and more.

Re-exports from flaqes.analysis.pattern_matcher for convenience.
"""

from flaqes.analysis.pattern_matcher import (
    DetectedPattern,
    PatternCategory,
    PatternDetector,
    PatternSignal,
    PatternType,
)

__all__ = [
    "DetectedPattern",
    "PatternCategory",
    "PatternDetector",
    "PatternSignal",
    "PatternType",
]
