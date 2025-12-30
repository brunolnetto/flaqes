"""
Pattern detection for common database design patterns.

This module detects structural and naming patterns that indicate specific
design decisions in a database schema:

- **Temporal Patterns**: SCD Type 1/2, event sourcing, versioning
- **Soft Delete Pattern**: Logical deletion markers
- **Polymorphic Association**: Type discriminators with nullable FKs
- **Audit Patterns**: Created/updated timestamps, user tracking
- **JSONB Patterns**: Schema flexibility indicators

Each pattern is detected with a confidence score and supporting signals.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import NamedTuple

from flaqes.core.schema_graph import SchemaGraph, Table
from flaqes.core.types import DataTypeCategory

# =============================================================================
# Pattern Types
# =============================================================================


class PatternType(Enum):
    """Types of database design patterns."""

    # Temporal patterns
    SCD_TYPE_1 = auto()  # Overwrites, no history
    SCD_TYPE_2 = auto()  # Validity period, full history
    SCD_TYPE_3 = auto()  # Previous value columns
    EVENT_SOURCING = auto()  # Immutable event log
    VERSIONED = auto()  # Version numbering

    # Deletion patterns
    SOFT_DELETE = auto()  # Logical delete flag
    TEMPORAL_DELETE = auto()  # Deleted_at timestamp

    # Association patterns
    POLYMORPHIC = auto()  # Type discriminator
    SINGLE_TABLE_INHERITANCE = auto()  # One table, type column

    # Audit patterns
    AUDIT_TIMESTAMPS = auto()  # Created/updated timestamps
    AUDIT_USER_TRACKING = auto()  # Created_by/updated_by
    FULL_AUDIT_TRAIL = auto()  # Separate audit log table

    # Flexibility patterns
    JSONB_SCHEMA = auto()  # JSONB for flexible fields
    EAV = auto()  # Entity-Attribute-Value

    # Other patterns
    OPTIMISTIC_LOCKING = auto()  # Version column for concurrency
    TREE_STRUCTURE = auto()  # Parent-child self-reference
    MATERIALIZED_PATH = auto()  # Path string for hierarchy


class PatternCategory(Enum):
    """Categories of patterns for grouping."""

    TEMPORAL = "temporal"
    DELETION = "deletion"
    ASSOCIATION = "association"
    AUDIT = "audit"
    FLEXIBILITY = "flexibility"
    CONCURRENCY = "concurrency"
    HIERARCHY = "hierarchy"


# =============================================================================
# Pattern Detection Results
# =============================================================================


class PatternSignal(NamedTuple):
    """Evidence supporting a pattern detection."""

    name: str
    description: str
    weight: float  # 0.0 to 1.0
    columns: tuple[str, ...] = ()


@dataclass
class DetectedPattern:
    """A detected pattern in a table."""

    pattern_type: PatternType
    table: str  # Table FQN
    confidence: float  # 0.0 to 1.0
    signals: list[PatternSignal] = field(default_factory=list)
    related_columns: tuple[str, ...] = ()
    description: str = ""

    @property
    def category(self) -> PatternCategory:
        """Get the category of this pattern."""
        category_map = {
            PatternType.SCD_TYPE_1: PatternCategory.TEMPORAL,
            PatternType.SCD_TYPE_2: PatternCategory.TEMPORAL,
            PatternType.SCD_TYPE_3: PatternCategory.TEMPORAL,
            PatternType.EVENT_SOURCING: PatternCategory.TEMPORAL,
            PatternType.VERSIONED: PatternCategory.TEMPORAL,
            PatternType.SOFT_DELETE: PatternCategory.DELETION,
            PatternType.TEMPORAL_DELETE: PatternCategory.DELETION,
            PatternType.POLYMORPHIC: PatternCategory.ASSOCIATION,
            PatternType.SINGLE_TABLE_INHERITANCE: PatternCategory.ASSOCIATION,
            PatternType.AUDIT_TIMESTAMPS: PatternCategory.AUDIT,
            PatternType.AUDIT_USER_TRACKING: PatternCategory.AUDIT,
            PatternType.FULL_AUDIT_TRAIL: PatternCategory.AUDIT,
            PatternType.JSONB_SCHEMA: PatternCategory.FLEXIBILITY,
            PatternType.EAV: PatternCategory.FLEXIBILITY,
            PatternType.OPTIMISTIC_LOCKING: PatternCategory.CONCURRENCY,
            PatternType.TREE_STRUCTURE: PatternCategory.HIERARCHY,
            PatternType.MATERIALIZED_PATH: PatternCategory.HIERARCHY,
        }
        return category_map.get(self.pattern_type, PatternCategory.AUDIT)

    @property
    def is_confident(self) -> bool:
        """Return True if confidence is above threshold (0.7)."""
        return self.confidence >= 0.7

    def summary(self) -> str:
        """Return a human-readable summary."""
        conf_pct = f"{self.confidence:.0%}"
        return f"{self.table}: {self.pattern_type.name} ({conf_pct})"


# =============================================================================
# Pattern Detection Functions
# =============================================================================


def _detect_scd_type_2(table: Table) -> DetectedPattern | None:
    """Detect Slowly Changing Dimension Type 2 pattern.

    SCD Type 2 maintains full history with validity periods.

    Signals:
    - valid_from/valid_to columns (or effective_date/end_date)
    - is_current flag column
    - No updated_at (records are immutable once closed)
    - Business key that repeats (not unique)
    """
    from flaqes.analysis.pattern_helpers import add_column_signal, find_column_by_names
    
    col_names = {c.name.lower() for c in table.columns}
    signals: list[PatternSignal] = []
    related_cols: list[str] = []

    # Check for validity period columns
    validity_from_names = {
        "valid_from",
        "effective_date",
        "start_date",
        "effective_from",
    }
    validity_to_names = {"valid_to", "end_date", "expiry_date", "effective_to"}

    from_col = find_column_by_names(col_names, validity_from_names)
    to_col = find_column_by_names(col_names, validity_to_names)

    if from_col and to_col:
        add_column_signal(
            signals,
            related_cols,
            "validity_period",
            f"Has validity period columns ({from_col}, {to_col})",
            0.8,
            from_col,
        )
        related_cols.append(to_col)  # Add second column separately
    elif from_col:
        add_column_signal(
            signals,
            related_cols,
            "validity_start",
            f"Has validity start column ({from_col})",
            0.4,
            from_col,
        )

    # Check for current flag
    current_flag_names = {"is_current", "current_flag", "active", "is_active"}
    flag_col = find_column_by_names(col_names, current_flag_names)
    add_column_signal(
        signals,
        related_cols,
        "current_flag",
        f"Has current record indicator ({flag_col})",
        0.5,
        flag_col,
    )

    # Check for version column
    version_names = {"version", "version_number", "revision", "row_version"}
    ver_col = find_column_by_names(col_names, version_names)
    add_column_signal(
        signals,
        related_cols,
        "version_column",
        f"Has version column ({ver_col})",
        0.4,
        ver_col,
    )

    # Anti-signal: has updated_at (suggests mutable records, not SCD2)
    if "updated_at" in col_names:
        signals.append(
            PatternSignal(
                name="updated_at_present",
                description="Has updated_at column (less likely to be SCD2)",
                weight=-0.3,
            )
        )

    # Calculate confidence
    if not signals:
        return None

    total_weight = sum(s.weight for s in signals)
    confidence = min(1.0, max(0.0, total_weight))

    # Let PatternDetector handle min_confidence filtering
    return DetectedPattern(
        pattern_type=PatternType.SCD_TYPE_2,
        table=table.fqn,
        confidence=confidence,
        signals=signals,
        related_columns=tuple(related_cols),
        description="Slowly Changing Dimension Type 2 pattern detected",
    )



def _detect_soft_delete(table: Table) -> DetectedPattern | None:
    """Detect soft delete pattern.

    Soft delete marks records as deleted without physically removing them.

    Signals:
    - is_deleted boolean column
    - deleted_at timestamp column
    - deleted_by user column
    - status column with 'deleted' value potential
    """
    col_names = {c.name.lower() for c in table.columns}
    columns_by_name = {c.name.lower(): c for c in table.columns}
    signals: list[PatternSignal] = []
    related_cols: list[str] = []

    # Check for deleted_at timestamp
    deleted_at_names = {"deleted_at", "deleted_date", "deletion_date", "removed_at"}
    for name in deleted_at_names:
        if name in col_names:
            col = columns_by_name[name]
            if col.data_type.category == DataTypeCategory.TIMESTAMP:
                signals.append(
                    PatternSignal(
                        name="deleted_at_timestamp",
                        description=f"Has nullable deleted timestamp ({name})",
                        weight=0.9,
                        columns=(name,),
                    )
                )
                related_cols.append(name)
                break

    # Check for is_deleted boolean
    deleted_flag_names = {"is_deleted", "deleted", "is_removed", "removed"}
    for name in deleted_flag_names:
        if name in col_names:
            col = columns_by_name[name]
            if col.data_type.category == DataTypeCategory.BOOLEAN:
                signals.append(
                    PatternSignal(
                        name="deleted_flag",
                        description=f"Has deleted flag column ({name})",
                        weight=0.9,
                        columns=(name,),
                    )
                )
                related_cols.append(name)
                break

    # Check for deleted_by
    deleted_by_names = {"deleted_by", "deleted_by_id", "removed_by"}
    for name in deleted_by_names:
        if name in col_names:
            signals.append(
                PatternSignal(
                    name="deleted_by",
                    description=f"Has deleted_by column ({name})",
                    weight=0.3,
                    columns=(name,),
                )
            )
            related_cols.append(name)
            break

    if not signals:
        return None

    total_weight = sum(s.weight for s in signals)
    confidence = min(1.0, total_weight)

    return DetectedPattern(
        pattern_type=PatternType.SOFT_DELETE
        if "deleted_flag" in [s.name for s in signals]
        else PatternType.TEMPORAL_DELETE,
        table=table.fqn,
        confidence=confidence,
        signals=signals,
        related_columns=tuple(related_cols),
        description="Soft delete pattern detected",
    )


def _detect_audit_timestamps(table: Table) -> DetectedPattern | None:
    """Detect audit timestamp pattern.

    Audit timestamps track when records were created and modified.

    Signals:
    - created_at/created_date timestamp
    - updated_at/modified_at timestamp
    """
    col_names = {c.name.lower() for c in table.columns}
    columns_by_name = {c.name.lower(): c for c in table.columns}
    signals: list[PatternSignal] = []
    related_cols: list[str] = []

    # Check for created_at
    created_names = {"created_at", "created_date", "create_time", "inserted_at"}
    for name in created_names:
        if name in col_names:
            col = columns_by_name[name]
            if col.data_type.category in (
                DataTypeCategory.TIMESTAMP,
                DataTypeCategory.DATE,
            ):
                signals.append(
                    PatternSignal(
                        name="created_timestamp",
                        description=f"Has creation timestamp ({name})",
                        weight=0.5,
                        columns=(name,),
                    )
                )
                related_cols.append(name)
                break

    # Check for updated_at
    updated_names = {"updated_at", "modified_at", "update_time", "last_modified"}
    for name in updated_names:
        if name in col_names:
            col = columns_by_name[name]
            if col.data_type.category in (
                DataTypeCategory.TIMESTAMP,
                DataTypeCategory.DATE,
            ):
                signals.append(
                    PatternSignal(
                        name="updated_timestamp",
                        description=f"Has update timestamp ({name})",
                        weight=0.5,
                        columns=(name,),
                    )
                )
                related_cols.append(name)
                break

    if not signals:
        return None

    total_weight = sum(s.weight for s in signals)
    confidence = min(1.0, total_weight)

    return DetectedPattern(
        pattern_type=PatternType.AUDIT_TIMESTAMPS,
        table=table.fqn,
        confidence=confidence,
        signals=signals,
        related_columns=tuple(related_cols),
        description="Audit timestamp pattern detected",
    )


def _detect_audit_user_tracking(table: Table) -> DetectedPattern | None:
    """Detect user tracking pattern.

    User tracking records who created/modified records.

    Signals:
    - created_by column
    - updated_by/modified_by column
    """
    col_names = {c.name.lower() for c in table.columns}
    signals: list[PatternSignal] = []
    related_cols: list[str] = []

    # Check for created_by
    created_by_names = {"created_by", "created_by_id", "creator_id", "author_id"}
    for name in created_by_names:
        if name in col_names:
            signals.append(
                PatternSignal(
                    name="created_by",
                    description=f"Has creator tracking ({name})",
                    weight=0.5,
                    columns=(name,),
                )
            )
            related_cols.append(name)
            break

    # Check for updated_by
    updated_by_names = {"updated_by", "modified_by", "updated_by_id", "modifier_id"}
    for name in updated_by_names:
        if name in col_names:
            signals.append(
                PatternSignal(
                    name="updated_by",
                    description=f"Has modifier tracking ({name})",
                    weight=0.5,
                    columns=(name,),
                )
            )
            related_cols.append(name)
            break

    if not signals:
        return None

    total_weight = sum(s.weight for s in signals)
    confidence = min(1.0, total_weight)

    return DetectedPattern(
        pattern_type=PatternType.AUDIT_USER_TRACKING,
        table=table.fqn,
        confidence=confidence,
        signals=signals,
        related_columns=tuple(related_cols),
        description="User tracking pattern detected",
    )


def _detect_polymorphic(table: Table) -> DetectedPattern | None:
    """Detect polymorphic association pattern.

    Polymorphic associations use a type discriminator to reference
    different target tables from a single column.

    Signals:
    - *_type column (entity_type, record_type, etc.)
    - *_id column that's not an FK (generic reference)
    - Multiple nullable FK columns (alternative approach)
    """
    col_names = {c.name.lower() for c in table.columns}
    columns_by_name = {c.name.lower(): c for c in table.columns}
    fk_columns = {col for fk in table.foreign_keys for col in fk.columns}

    signals: list[PatternSignal] = []
    related_cols: list[str] = []

    # Check for type discriminator columns
    type_col = _find_type_discriminator(col_names, columns_by_name)
    if type_col:
        signals.append(
            PatternSignal(
                name="type_discriminator",
                description=f"Has type discriminator column ({type_col})",
                weight=0.6,
                columns=(type_col,),
            )
        )
        related_cols.append(type_col)

    # Check for generic ID columns not backed by FK
    generic_ids = _find_generic_ids(col_names, fk_columns)
    if generic_ids and type_col:
        signals.append(
            PatternSignal(
                name="generic_id",
                description=f"Has generic ID columns without FK ({', '.join(generic_ids[:3])})",
                weight=0.5,
                columns=tuple(generic_ids[:3]),
            )
        )
        related_cols.extend(generic_ids[:3])

    # Check for multiple nullable FKs (alternative polymorphic pattern)
    nullable_fk_count = _count_nullable_fks(table.foreign_keys, columns_by_name)
    if nullable_fk_count >= 2:
        signals.append(
            PatternSignal(
                name="multiple_nullable_fks",
                description=f"Has {nullable_fk_count} nullable FK columns",
                weight=0.4,
            )
        )

    if not signals:
        return None

    total_weight = sum(s.weight for s in signals)
    confidence = min(1.0, total_weight)

    # Let PatternDetector handle min_confidence filtering
    return DetectedPattern(
        pattern_type=PatternType.POLYMORPHIC,
        table=table.fqn,
        confidence=confidence,
        signals=signals,
        related_columns=tuple(related_cols),
        description="Polymorphic association pattern detected",
    )


def _find_type_discriminator(col_names: set[str], columns_by_name: dict) -> str | None:
    """Find a type discriminator column."""
    type_col_patterns = ["_type", "type_"]
    type_cols = [
        name
        for name in col_names
        if any(p in name for p in type_col_patterns) or name == "type"
    ]

    for type_col in type_cols:
        col = columns_by_name[type_col]
        if col.data_type.category == DataTypeCategory.TEXT:
            return type_col
    return None


def _find_generic_ids(col_names: set[str], fk_columns: set[str]) -> list[str]:
    """Find ID columns that aren't backed by foreign keys."""
    id_cols = [name for name in col_names if name.endswith("_id")]
    return [name for name in id_cols if name not in {c.lower() for c in fk_columns}]


def _count_nullable_fks(foreign_keys, columns_by_name: dict) -> int:
    """Count foreign keys where all columns are nullable."""
    nullable_fks = [
        fk
        for fk in foreign_keys
        if all(
            columns_by_name.get(c.lower(), columns_by_name.get(c))
            and columns_by_name.get(c.lower(), columns_by_name.get(c)).nullable
            for c in fk.columns
        )
    ]
    return len(nullable_fks)



def _detect_jsonb_schema(table: Table) -> DetectedPattern | None:
    """Detect JSONB schema flexibility pattern.

    JSONB columns often indicate schema flexibility needs.

    Signals:
    - JSON/JSONB columns
    - Column names like 'data', 'metadata', 'properties', 'attributes'
    """
    signals: list[PatternSignal] = []
    related_cols: list[str] = []

    json_columns = [
        c for c in table.columns if c.data_type.category == DataTypeCategory.JSON
    ]

    if not json_columns:
        return None

    # High-signal JSON column names
    significant_names = {
        "data",
        "metadata",
        "properties",
        "attributes",
        "config",
        "payload",
        "extra",
    }

    for col in json_columns:
        weight = 0.7 if col.name.lower() in significant_names else 0.4
        signals.append(
            PatternSignal(
                name="json_column",
                description=f"Has JSON/JSONB column ({col.name})",
                weight=weight,
                columns=(col.name,),
            )
        )
        related_cols.append(col.name)

    total_weight = min(1.0, sum(s.weight for s in signals))

    return DetectedPattern(
        pattern_type=PatternType.JSONB_SCHEMA,
        table=table.fqn,
        confidence=total_weight,
        signals=signals,
        related_columns=tuple(related_cols),
        description="JSONB schema flexibility pattern detected",
    )


def _detect_optimistic_locking(table: Table) -> DetectedPattern | None:
    """Detect optimistic locking pattern.

    Optimistic locking uses version columns for concurrency control.

    Signals:
    - version/row_version column
    - lock_version column
    - xmin column usage hints
    """
    col_names = {c.name.lower() for c in table.columns}
    columns_by_name = {c.name.lower(): c for c in table.columns}
    signals: list[PatternSignal] = []
    related_cols: list[str] = []

    version_names = {
        "version",
        "row_version",
        "lock_version",
        "optimistic_lock_version",
    }

    for name in version_names:
        if name in col_names:
            col = columns_by_name[name]
            # Version column should be integer-ish
            if col.data_type.category in (
                DataTypeCategory.INTEGER,
                DataTypeCategory.DECIMAL,
            ):
                signals.append(
                    PatternSignal(
                        name="version_column",
                        description=f"Has version column for optimistic locking ({name})",
                        weight=0.9,
                        columns=(name,),
                    )
                )
                related_cols.append(name)
                break

    if not signals:
        return None

    return DetectedPattern(
        pattern_type=PatternType.OPTIMISTIC_LOCKING,
        table=table.fqn,
        confidence=sum(s.weight for s in signals),
        signals=signals,
        related_columns=tuple(related_cols),
        description="Optimistic locking pattern detected",
    )


def _detect_tree_structure(table: Table, graph: SchemaGraph) -> DetectedPattern | None:
    """Detect tree/hierarchy structure pattern.

    Self-referencing tables often represent hierarchies.

    Signals:
    - FK pointing to same table (parent_id)
    - Columns named parent_id, parent, manager_id
    - Path column for materialized path
    """
    signals: list[PatternSignal] = []
    related_cols: list[str] = []
    col_names = {c.name.lower() for c in table.columns}

    # Check for self-referencing FK
    self_refs = [fk for fk in table.foreign_keys if fk.target_table == table.name]

    for fk in self_refs:
        signals.append(
            PatternSignal(
                name="self_reference",
                description=f"Self-referencing FK ({fk.name})",
                weight=0.8,
                columns=fk.columns,
            )
        )
        related_cols.extend(fk.columns)

    # Check for parent column without FK (may be implicit hierarchy)
    parent_names = {"parent_id", "parent", "manager_id", "supervisor_id", "reports_to"}
    for name in parent_names:
        if name in col_names and not any(
            name in fk.columns for fk in table.foreign_keys
        ):
            signals.append(
                PatternSignal(
                    name="parent_column",
                    description=f"Has parent-like column ({name})",
                    weight=0.5,
                    columns=(name,),
                )
            )
            related_cols.append(name)
            break

    # Check for materialized path column
    path_names = {"path", "tree_path", "hierarchy_path", "ltree"}
    for name in path_names:
        if name in col_names:
            signals.append(
                PatternSignal(
                    name="path_column",
                    description=f"Has path column ({name}) - materialized path pattern",
                    weight=0.7,
                    columns=(name,),
                )
            )
            related_cols.append(name)
            break

    if not signals:
        return None

    total_weight = sum(s.weight for s in signals)
    confidence = min(1.0, total_weight)

    # Determine if it's tree or materialized path
    pattern_type = PatternType.TREE_STRUCTURE
    if any(s.name == "path_column" for s in signals):
        pattern_type = PatternType.MATERIALIZED_PATH

    return DetectedPattern(
        pattern_type=pattern_type,
        table=table.fqn,
        confidence=confidence,
        signals=signals,
        related_columns=tuple(related_cols),
        description="Tree/hierarchy structure pattern detected",
    )


def _detect_event_sourcing(table: Table) -> DetectedPattern | None:
    """Detect event sourcing pattern.

    Event sourcing tables store immutable events.

    Signals:
    - Table name contains 'event', 'log', 'audit'
    - Has created_at but no updated_at
    - Has event_type/action column
    - Has payload/data JSON column
    - Append-only structure (no update signals)
    """
    col_names = {c.name.lower() for c in table.columns}
    table_name_lower = table.name.lower()
    signals: list[PatternSignal] = []
    related_cols: list[str] = []

    # Check table name
    event_table_patterns = ["event", "log", "audit", "history", "changelog"]
    if any(p in table_name_lower for p in event_table_patterns):
        signals.append(
            PatternSignal(
                name="event_table_name",
                description=f"Table name suggests event storage ({table.name})",
                weight=0.4,
            )
        )

    # Check for created_at without updated_at (suggests immutable)
    has_created = any(
        n in col_names for n in {"created_at", "occurred_at", "timestamp"}
    )
    has_updated = any(n in col_names for n in {"updated_at", "modified_at"})

    if has_created and not has_updated:
        signals.append(
            PatternSignal(
                name="immutable_timestamps",
                description="Has creation timestamp without update timestamp",
                weight=0.5,
            )
        )

    # Check for event type column
    event_type_names = {"event_type", "action", "operation", "event_name"}
    for name in event_type_names:
        if name in col_names:
            signals.append(
                PatternSignal(
                    name="event_type",
                    description=f"Has event type column ({name})",
                    weight=0.4,
                    columns=(name,),
                )
            )
            related_cols.append(name)
            break

    # Check for payload column
    payload_names = {"payload", "data", "event_data", "details"}
    for name in payload_names:
        if name in col_names:
            col = next((c for c in table.columns if c.name.lower() == name), None)
            if col and col.data_type.category == DataTypeCategory.JSON:
                signals.append(
                    PatternSignal(
                        name="payload_column",
                        description=f"Has JSON payload column ({name})",
                        weight=0.4,
                        columns=(name,),
                    )
                )
                related_cols.append(name)
                break

    if not signals:
        return None

    total_weight = sum(s.weight for s in signals)
    confidence = min(1.0, total_weight)

    # Let PatternDetector handle min_confidence filtering
    return DetectedPattern(
        pattern_type=PatternType.EVENT_SOURCING,
        table=table.fqn,
        confidence=confidence,
        signals=signals,
        related_columns=tuple(related_cols),
        description="Event sourcing pattern detected",
    )


# =============================================================================
# Pattern Detector Class
# =============================================================================


class PatternDetector:
    """Main class for detecting design patterns in a schema.

    Example:
        >>> detector = PatternDetector()
        >>> patterns = detector.detect_all(table, graph)
        >>> for pattern in patterns:
        ...     print(pattern.summary())
    """

    def __init__(self, min_confidence: float = 0.3) -> None:
        """Initialize the pattern detector.

        Args:
            min_confidence: Minimum confidence threshold for pattern detection.
        """
        self.min_confidence = min_confidence

    def detect_all(
        self,
        table: Table,
        graph: SchemaGraph,
    ) -> list[DetectedPattern]:
        """Detect all patterns in a table.

        Args:
            table: The table to analyze.
            graph: The full schema graph for context.

        Returns:
            List of detected patterns, sorted by confidence (descending).
        """
        patterns: list[DetectedPattern] = []

        # Run all detection functions
        detectors = [
            lambda t: _detect_scd_type_2(t),
            lambda t: _detect_soft_delete(t),
            lambda t: _detect_audit_timestamps(t),
            lambda t: _detect_audit_user_tracking(t),
            lambda t: _detect_polymorphic(t),
            lambda t: _detect_jsonb_schema(t),
            lambda t: _detect_optimistic_locking(t),
            lambda t: _detect_tree_structure(t, graph),
            lambda t: _detect_event_sourcing(t),
        ]

        for detector in detectors:
            result = detector(table)
            if result and result.confidence >= self.min_confidence:
                patterns.append(result)

        # Sort by confidence (highest first)
        patterns.sort(key=lambda p: p.confidence, reverse=True)

        return patterns

    def detect_pattern(
        self,
        table: Table,
        pattern_type: PatternType,
        graph: SchemaGraph | None = None,
    ) -> DetectedPattern | None:
        """Detect a specific pattern type in a table.

        Args:
            table: The table to analyze.
            pattern_type: The specific pattern to look for.
            graph: Optional schema graph for context.

        Returns:
            DetectedPattern if found, None otherwise.
        """
        detector_map = {
            PatternType.SCD_TYPE_2: lambda: _detect_scd_type_2(table),
            PatternType.SOFT_DELETE: lambda: _detect_soft_delete(table),
            PatternType.TEMPORAL_DELETE: lambda: _detect_soft_delete(table),
            PatternType.AUDIT_TIMESTAMPS: lambda: _detect_audit_timestamps(table),
            PatternType.AUDIT_USER_TRACKING: lambda: _detect_audit_user_tracking(table),
            PatternType.POLYMORPHIC: lambda: _detect_polymorphic(table),
            PatternType.JSONB_SCHEMA: lambda: _detect_jsonb_schema(table),
            PatternType.OPTIMISTIC_LOCKING: lambda: _detect_optimistic_locking(table),
            PatternType.TREE_STRUCTURE: lambda: _detect_tree_structure(
                table, graph or SchemaGraph()
            ),
            PatternType.MATERIALIZED_PATH: lambda: _detect_tree_structure(
                table, graph or SchemaGraph()
            ),
            PatternType.EVENT_SOURCING: lambda: _detect_event_sourcing(table),
        }

        detector = detector_map.get(pattern_type)
        if detector:
            result = detector()
            if result and result.confidence >= self.min_confidence:
                return result

        return None

    def detect_schema_patterns(
        self,
        graph: SchemaGraph,
    ) -> dict[str, list[DetectedPattern]]:
        """Detect patterns across all tables in a schema.

        Args:
            graph: The schema graph to analyze.

        Returns:
            Dictionary mapping table FQN to list of detected patterns.
        """
        result: dict[str, list[DetectedPattern]] = {}

        for table in graph:
            patterns = self.detect_all(table, graph)
            if patterns:
                result[table.fqn] = patterns

        return result
