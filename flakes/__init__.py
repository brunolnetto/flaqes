"""
flakes - A schema critic for PostgreSQL databases.

flakes analyzes database structures and surfaces design tensions,
trade-offs, and alternative approaches based on your stated intent.
"""

from flakes.api import analyze_schema, introspect_schema
from flakes.analysis import (
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
from flakes.core.intent import Intent
from flakes.core.schema_graph import (
    Column,
    Constraint,
    ForeignKey,
    Index,
    PrimaryKey,
    Relationship,
    SchemaGraph,
    Table,
)
from flakes.core.types import (
    Cardinality,
    ConstraintType,
    DataTypeCategory,
    IndexMethod,
    RoleType,
    Severity,
    TensionCategory,
)
from flakes.introspection import (
    Introspector,
    IntrospectorProtocol,
    get_introspector,
    register_introspector,
)
from flakes.introspection.base import (
    IntrospectionConfig,
    IntrospectionError,
    IntrospectionResult,
)
from flakes.report import SchemaReport, generate_report

# Database-specific introspectors are registered lazily.
# Import them explicitly to register:
#   import flakes.introspection.postgresql
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


