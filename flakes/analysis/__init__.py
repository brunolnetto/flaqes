"""Analysis module for schema understanding, pattern detection, and tension analysis."""

from flakes.analysis.pattern_matcher import (
    DetectedPattern,
    PatternCategory,
    PatternDetector,
    PatternSignal,
    PatternType,
)
from flakes.analysis.role_detector import (
    RoleDetector,
    Signal,
    TableRoleResult,
)
from flakes.analysis.tension_analyzer import (
    Alternative,
    DesignTension,
    Effort,
    TensionAnalyzer,
    TensionSignal,
)

__all__ = [
    # Role detection
    "RoleDetector",
    "TableRoleResult",
    "Signal",
    # Pattern matching
    "DetectedPattern",
    "PatternCategory",
    "PatternDetector",
    "PatternSignal",
    "PatternType",
    # Tension analysis
    "TensionAnalyzer",
    "DesignTension",
    "Alternative",
    "Effort",
    "TensionSignal",
]


