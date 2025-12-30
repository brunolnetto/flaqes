"""
Core type definitions for flakes.

This module contains all enums, literals, and type aliases used throughout
the library. Centralizing types here ensures consistency and makes it easy
to understand the vocabulary of the domain.
"""

from enum import Enum, auto
from typing import Literal

# =============================================================================
# Workload & Intent Types
# =============================================================================

Workload = Literal["OLTP", "OLAP", "mixed"]
"""The primary workload type for the database."""

WriteFrequency = Literal["high", "medium", "low"]
"""How often data is written to the database."""

ReadPattern = Literal["point_lookup", "range_scan", "aggregation", "join_heavy"]
"""Common read access patterns."""

ConsistencyLevel = Literal["strong", "eventual"]
"""Required consistency guarantees."""

EvolutionRate = Literal["high", "medium", "low", "frozen"]
"""How frequently the schema is expected to change."""

DataVolume = Literal["small", "medium", "large", "massive"]
"""
Approximate data volume classification.
- small: < 100K rows
- medium: 100K - 10M rows  
- large: 10M - 1B rows
- massive: > 1B rows
"""

Engine = Literal["postgresql", "mysql", "sqlite"]
"""
Supported database engines.

To add a new engine:
1. Add the engine name to this Literal type
2. Create flakes/introspection/<engine>.py implementing Introspector
3. Use @register_introspector("<engine>") decorator on the class

PostgreSQL is the primary supported engine for v1.
MySQL and SQLite are placeholders for future implementation.
"""


# =============================================================================
# Schema Structure Types
# =============================================================================


class Cardinality(Enum):
    """Relationship cardinality between tables."""

    ONE_TO_ONE = auto()
    ONE_TO_MANY = auto()
    MANY_TO_ONE = auto()
    MANY_TO_MANY = auto()  # Via junction table


class ConstraintType(Enum):
    """Types of database constraints."""

    PRIMARY_KEY = auto()
    FOREIGN_KEY = auto()
    UNIQUE = auto()
    CHECK = auto()
    EXCLUSION = auto()
    NOT_NULL = auto()


class IndexMethod(Enum):
    """PostgreSQL index access methods."""

    BTREE = "btree"
    HASH = "hash"
    GIN = "gin"
    GIST = "gist"
    SPGIST = "spgist"
    BRIN = "brin"


class DataTypeCategory(Enum):
    """
    High-level categorization of column data types.
    
    This abstraction allows pattern matching without caring about
    the exact type (e.g., INT2 vs INT4 vs INT8 all map to INTEGER).
    """

    INTEGER = auto()
    FLOAT = auto()
    DECIMAL = auto()
    TEXT = auto()
    BOOLEAN = auto()
    TIMESTAMP = auto()
    DATE = auto()
    TIME = auto()
    INTERVAL = auto()
    UUID = auto()
    JSON = auto()
    ARRAY = auto()
    BINARY = auto()
    ENUM = auto()
    COMPOSITE = auto()
    RANGE = auto()
    GEOMETRIC = auto()
    NETWORK = auto()
    OTHER = auto()


# =============================================================================
# Semantic Analysis Types
# =============================================================================


class RoleType(Enum):
    """
    Semantic role hypothesis for a table.
    
    These are not mutually exclusive in reality, but we pick the
    most likely primary role and track alternatives with confidence.
    """

    # Dimensional modeling roles
    FACT = auto()
    """Measures/metrics table, typically FK-heavy with numeric columns."""

    DIMENSION = auto()
    """Descriptive attributes table, typically referenced by facts."""

    # Temporal patterns
    EVENT = auto()
    """Append-only event log, immutable after creation."""

    SNAPSHOT = auto()
    """Point-in-time state capture, typically periodic."""

    SCD_TYPE_1 = auto()
    """Slowly Changing Dimension with in-place updates."""

    SCD_TYPE_2 = auto()
    """Slowly Changing Dimension with history tracking."""

    # Structural roles
    JUNCTION = auto()
    """Many-to-many relationship bridge table."""

    LOOKUP = auto()
    """Small reference/config table (countries, statuses, etc.)."""

    POLYMORPHIC = auto()
    """Single table storing multiple entity types via discriminator."""

    # Catch-all
    ENTITY = auto()
    """Generic domain entity, no specific pattern detected."""

    UNKNOWN = auto()
    """Insufficient signals to determine role."""


class TensionCategory(Enum):
    """Categories of design tensions."""

    NORMALIZATION = auto()
    """Trade-offs related to normal forms and denormalization."""

    PERFORMANCE = auto()
    """Trade-offs affecting query or write performance."""

    EVOLUTION = auto()
    """Trade-offs affecting schema changeability."""

    CONSISTENCY = auto()
    """Trade-offs affecting data integrity and consistency."""

    COMPLEXITY = auto()
    """Trade-offs affecting cognitive load and maintainability."""


class Severity(Enum):
    """Severity levels for design tensions."""

    INFO = auto()
    """Informational, worth knowing but not actionable."""

    WARNING = auto()
    """Potential issue depending on intent and scale."""

    CRITICAL = auto()
    """Likely to cause problems, warrants immediate attention."""


class Effort(Enum):
    """Estimated effort to implement an alternative design."""

    LOW = auto()
    """Simple change, minimal risk (e.g., add an index)."""

    MEDIUM = auto()
    """Moderate change, some migration effort (e.g., split a table)."""

    HIGH = auto()
    """Significant refactoring, high risk (e.g., change data model)."""
