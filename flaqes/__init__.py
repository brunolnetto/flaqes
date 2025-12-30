"""
flaqes - A schema critic for PostgreSQL databases.

flaqes analyzes database structures and surfaces design tensions,
trade-offs, and alternative approaches based on your stated intent.
"""

from flaqes.analysis import (
    Alternative,
    DesignTension,
    DetectedPattern,
    Effort,
    PatternCategory,
    PatternDetector,
    PatternSignal,
    PatternType,
    RoleDetector,
    Signal,
    TableRoleResult,
    TensionAnalyzer,
    TensionSignal,
)
from flaqes.api import analyze_schema, introspect_schema
from flaqes.core.intent import Intent
from flaqes.core.schema_graph import (
    Column,
    Constraint,
    ForeignKey,
    Index,
    PrimaryKey,
    Relationship,
    SchemaGraph,
    Table,
)
from flaqes.core.types import (
    Cardinality,
    ConstraintType,
    DataTypeCategory,
    IndexMethod,
    RoleType,
    Severity,
    TensionCategory,
)
from flaqes.introspection import (
    Introspector,
    IntrospectorProtocol,
    get_introspector,
    register_introspector,
)
from flaqes.introspection.base import (
    IntrospectionConfig,
    IntrospectionError,
    IntrospectionResult,
)
from flaqes.report import SchemaReport, generate_report

# Database-specific introspectors are registered lazily.
# Import them explicitly to register:
#   import flaqes.introspection.postgresql
# Or use get_introspector() which auto-registers on first use.

__version__ = "0.1.0"
__all__ = [
    # Main API
    "analyze_schema",
    "introspect_schema",
    # Intent
    "Intent",
    # Schema Graph
    "SchemaGraph",
    "Table",
    "Column",
    "PrimaryKey",
    "ForeignKey",
    "Constraint",
    "Index",
    "Relationship",
    # Types
    "Cardinality",
    "ConstraintType",
    "DataTypeCategory",
    "IndexMethod",
    "RoleType",
    "Severity",
    "TensionCategory",
    # Introspection
    "Introspector",
    "IntrospectorProtocol",
    "IntrospectionConfig",
    "IntrospectionResult",
    "IntrospectionError",
    "get_introspector",
    "register_introspector",
    # Analysis - Role Detection
    "RoleDetector",
    "TableRoleResult",
    "Signal",
    # Analysis - Pattern Matching
    "PatternDetector",
    "DetectedPattern",
    "PatternType",
    "PatternCategory",
    "PatternSignal",
    # Analysis - Tension Analysis
    "TensionAnalyzer",
    "DesignTension",
    "Alternative",
    "Effort",
    "TensionSignal",
    # Report
    "SchemaReport",
    "generate_report",
]
