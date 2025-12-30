"""
Table role detection based on structural signals.

This module implements heuristic-based detection of table semantic roles
(fact, dimension, event, junction, etc.) by analyzing structural patterns
in the schema.

The key principle: we don't claim certainty. Every detection comes with
a confidence score and the signals that led to that conclusion.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

from flakes.core.schema_graph import SchemaGraph, Table
from flakes.core.types import DataTypeCategory, RoleType


# =============================================================================
# Signal Types
# =============================================================================


class SignalType(Enum):
    """Categories of signals used for role detection."""

    STRUCTURAL = auto()
    """Based on keys, constraints, relationships."""

    NAMING = auto()
    """Based on column/table naming conventions."""

    DATA_TYPE = auto()
    """Based on column data types."""

    CARDINALITY = auto()
    """Based on relationship cardinalities."""


@dataclass(frozen=True, slots=True)
class Signal:
    """
    A piece of evidence supporting a role hypothesis.
    
    Signals are the building blocks of role detection. Each signal
    represents an observable fact about the table that suggests
    a particular role.
    """

    name: str
    """Short identifier for the signal (e.g., 'has_composite_pk')."""

    description: str
    """Human-readable description of what was observed."""

    signal_type: SignalType
    """Category of this signal."""

    weight: float = 1.0
    """
    How strongly this signal indicates the role (0.0 to 1.0).
    Higher weight = stronger evidence.
    """

    def __str__(self) -> str:
        return f"{self.name}: {self.description}"


@dataclass(slots=True)
class TableRoleResult:
    """
    Result of role detection for a single table.
    
    Contains the primary role hypothesis with confidence, plus
    alternative interpretations and the signals that led to each.
    """

    table: str
    """Fully qualified table name."""

    primary_role: RoleType
    """Most likely role based on signals."""

    confidence: float
    """Confidence in primary role (0.0 to 1.0)."""

    signals: list[Signal] = field(default_factory=list)
    """Signals that contributed to the primary role."""

    alternatives: list[tuple[RoleType, float]] = field(default_factory=list)
    """Alternative roles with their confidence scores."""

    @property
    def is_confident(self) -> bool:
        """Whether we have high confidence (>0.7) in the primary role."""
        return self.confidence > 0.7

    @property
    def is_ambiguous(self) -> bool:
        """Whether there are close alternative interpretations."""
        if not self.alternatives:
            return False
        top_alt_confidence = self.alternatives[0][1]
        return (self.confidence - top_alt_confidence) < 0.2

    def summary(self) -> str:
        """Return a human-readable summary."""
        conf_pct = f"{self.confidence:.0%}"
        result = f"{self.table}: {self.primary_role.name} ({conf_pct})"
        if self.is_ambiguous and self.alternatives:
            alt_role, alt_conf = self.alternatives[0]
            result += f" [also possibly {alt_role.name} at {alt_conf:.0%}]"
        return result


# =============================================================================
# Signal Detectors
# =============================================================================


def _detect_junction_signals(table: Table, graph: SchemaGraph) -> list[Signal]:
    """Detect signals indicating a junction (bridge) table."""
    signals: list[Signal] = []

    # Signal: Composite PK made entirely of FKs
    if table.primary_key and table.primary_key.is_composite:
        pk_cols = set(table.primary_key.columns)
        fk_cols: set[str] = set()
        for fk in table.foreign_keys:
            fk_cols.update(fk.columns)

        if pk_cols == fk_cols:
            signals.append(Signal(
                name="pk_is_fk_composite",
                description="Primary key consists entirely of foreign key columns",
                signal_type=SignalType.STRUCTURAL,
                weight=0.9,
            ))
        elif pk_cols.issubset(fk_cols):
            signals.append(Signal(
                name="pk_subset_of_fks",
                description="Primary key is a subset of foreign key columns",
                signal_type=SignalType.STRUCTURAL,
                weight=0.7,
            ))

    # Signal: Exactly 2 FKs (classic many-to-many bridge)
    if len(table.foreign_keys) == 2:
        signals.append(Signal(
            name="exactly_two_fks",
            description="Table has exactly two foreign keys (many-to-many bridge)",
            signal_type=SignalType.STRUCTURAL,
            weight=0.6,
        ))

    # Signal: Minimal additional columns (just the FKs + maybe timestamps)
    # Only check this if we have foreign keys
    if table.foreign_keys:
        non_fk_cols = [
            c for c in table.columns
            if c.name not in {col for fk in table.foreign_keys for col in fk.columns}
        ]
        # Allow for audit columns like created_at
        non_audit_cols = [
            c for c in non_fk_cols
            if c.name not in {"created_at", "updated_at", "id"}
        ]
        if len(non_audit_cols) <= 2:
            signals.append(Signal(
                name="minimal_payload",
                description="Table has minimal columns beyond foreign keys",
                signal_type=SignalType.STRUCTURAL,
                weight=0.5,
            ))

    return signals


def _detect_fact_signals(table: Table, graph: SchemaGraph) -> list[Signal]:
    """Detect signals indicating a fact table."""
    signals: list[Signal] = []

    # Signal: Many foreign keys (dimension references)
    if len(table.foreign_keys) >= 3:
        signals.append(Signal(
            name="many_fks",
            description=f"Table has {len(table.foreign_keys)} foreign keys (dimension references)",
            signal_type=SignalType.STRUCTURAL,
            weight=0.6,
        ))

    # Signal: Numeric measure columns
    numeric_cols = [
        c for c in table.columns
        if c.data_type.category in (
            DataTypeCategory.INTEGER,
            DataTypeCategory.FLOAT,
            DataTypeCategory.DECIMAL,
        )
        # Exclude likely ID columns
        and not c.name.endswith("_id")
        and c.name != "id"
        and not c.is_identity
    ]
    if len(numeric_cols) >= 2:
        signals.append(Signal(
            name="numeric_measures",
            description=f"Table has {len(numeric_cols)} numeric columns (potential measures)",
            signal_type=SignalType.DATA_TYPE,
            weight=0.5,
        ))

    # Signal: Timestamp column (event time)
    ts_cols = table.timestamp_columns
    event_time_names = {"created_at", "event_time", "timestamp", "occurred_at", "transaction_date"}
    has_event_time = any(c.name.lower() in event_time_names for c in ts_cols)
    if has_event_time:
        signals.append(Signal(
            name="event_timestamp",
            description="Table has an event/transaction timestamp column",
            signal_type=SignalType.NAMING,
            weight=0.4,
        ))

    # Signal: Table name suggests facts
    fact_name_patterns = {"fact", "facts", "transactions", "events", "orders", "sales", "payments"}
    if any(p in table.name.lower() for p in fact_name_patterns):
        signals.append(Signal(
            name="fact_table_name",
            description=f"Table name '{table.name}' suggests a fact table",
            signal_type=SignalType.NAMING,
            weight=0.4,
        ))

    # Signal: Wide table (many columns)
    if len(table.columns) >= 10:
        signals.append(Signal(
            name="wide_table",
            description=f"Table has {len(table.columns)} columns (wide table)",
            signal_type=SignalType.STRUCTURAL,
            weight=0.3,
        ))

    return signals


def _detect_dimension_signals(table: Table, graph: SchemaGraph) -> list[Signal]:
    """Detect signals indicating a dimension table."""
    signals: list[Signal] = []

    # Signal: Referenced by other tables (incoming FKs)
    referencing_tables = graph.tables_referencing(table.fqn)
    if len(referencing_tables) >= 2:
        signals.append(Signal(
            name="heavily_referenced",
            description=f"Table is referenced by {len(referencing_tables)} other tables",
            signal_type=SignalType.CARDINALITY,
            weight=0.7,
        ))
    elif len(referencing_tables) == 1:
        signals.append(Signal(
            name="referenced",
            description="Table is referenced by another table",
            signal_type=SignalType.CARDINALITY,
            weight=0.4,
        ))

    # Signal: Few or no outgoing FKs (dimensions don't reference facts)
    if len(table.foreign_keys) == 0:
        signals.append(Signal(
            name="no_outgoing_fks",
            description="Table has no foreign keys (leaf in reference graph)",
            signal_type=SignalType.STRUCTURAL,
            weight=0.5,
        ))
    elif len(table.foreign_keys) == 1:
        signals.append(Signal(
            name="single_outgoing_fk",
            description="Table has only one foreign key",
            signal_type=SignalType.STRUCTURAL,
            weight=0.3,
        ))

    # Signal: Text-heavy (descriptive attributes)
    text_cols = table.columns_by_category(DataTypeCategory.TEXT)
    if len(text_cols) >= 3:
        signals.append(Signal(
            name="text_heavy",
            description=f"Table has {len(text_cols)} text columns (descriptive attributes)",
            signal_type=SignalType.DATA_TYPE,
            weight=0.4,
        ))

    # Signal: Dimension naming patterns
    dim_name_patterns = {
        "dim", "dimension", "lookup", "type", "status", "category",
        "customer", "product", "user", "account", "store", "region",
    }
    if any(p in table.name.lower() for p in dim_name_patterns):
        signals.append(Signal(
            name="dimension_table_name",
            description=f"Table name '{table.name}' suggests a dimension",
            signal_type=SignalType.NAMING,
            weight=0.4,
        ))

    # Signal: Surrogate key (typical for dimensions)
    if table.has_surrogate_key:
        signals.append(Signal(
            name="surrogate_key",
            description="Table has an auto-generated surrogate key",
            signal_type=SignalType.STRUCTURAL,
            weight=0.3,
        ))

    return signals


def _detect_event_signals(table: Table, graph: SchemaGraph) -> list[Signal]:
    """Detect signals indicating an event/log table."""
    signals: list[Signal] = []

    # Signal: created_at without updated_at (append-only)
    col_names = {c.name.lower() for c in table.columns}
    has_created = any(n in col_names for n in {"created_at", "created", "timestamp", "event_time"})
    has_updated = any(n in col_names for n in {"updated_at", "updated", "modified_at", "modified"})

    if has_created and not has_updated:
        signals.append(Signal(
            name="append_only_timestamps",
            description="Has creation timestamp but no update timestamp (append-only pattern)",
            signal_type=SignalType.NAMING,
            weight=0.7,
        ))

    # Signal: Event naming patterns
    event_name_patterns = {
        "event", "events", "log", "logs", "audit", "history",
        "activity", "activities", "stream", "changes",
    }
    if any(p in table.name.lower() for p in event_name_patterns):
        signals.append(Signal(
            name="event_table_name",
            description=f"Table name '{table.name}' suggests an event/log table",
            signal_type=SignalType.NAMING,
            weight=0.6,
        ))

    # Signal: Event type discriminator
    type_cols = [
        c for c in table.columns
        if c.name.lower() in {"event_type", "type", "action", "operation", "kind"}
    ]
    if type_cols:
        signals.append(Signal(
            name="event_type_column",
            description="Has a type/action discriminator column",
            signal_type=SignalType.NAMING,
            weight=0.5,
        ))

    # Signal: JSON payload column (flexible event data)
    if table.json_columns:
        signals.append(Signal(
            name="json_payload",
            description="Has JSON column (flexible event payload)",
            signal_type=SignalType.DATA_TYPE,
            weight=0.4,
        ))

    return signals


def _detect_scd_type2_signals(table: Table, graph: SchemaGraph) -> list[Signal]:
    """Detect signals indicating a Slowly Changing Dimension Type 2."""
    signals: list[Signal] = []
    col_names = {c.name.lower() for c in table.columns}

    # Signal: Valid from/to columns
    has_valid_from = any(n in col_names for n in {"valid_from", "effective_from", "start_date", "from_date"})
    has_valid_to = any(n in col_names for n in {"valid_to", "effective_to", "end_date", "to_date"})

    if has_valid_from and has_valid_to:
        signals.append(Signal(
            name="validity_period",
            description="Has valid_from and valid_to columns (SCD Type 2 pattern)",
            signal_type=SignalType.NAMING,
            weight=0.9,
        ))
    elif has_valid_from:
        signals.append(Signal(
            name="valid_from_only",
            description="Has valid_from column (possible SCD)",
            signal_type=SignalType.NAMING,
            weight=0.4,
        ))

    # Signal: is_current flag
    has_is_current = any(n in col_names for n in {"is_current", "is_active", "current_flag"})
    if has_is_current:
        signals.append(Signal(
            name="is_current_flag",
            description="Has is_current boolean flag",
            signal_type=SignalType.NAMING,
            weight=0.7,
        ))

    # Signal: Version column
    has_version = any(n in col_names for n in {"version", "version_number", "revision"})
    if has_version:
        signals.append(Signal(
            name="version_column",
            description="Has version/revision column",
            signal_type=SignalType.NAMING,
            weight=0.5,
        ))

    return signals


def _detect_lookup_signals(table: Table, graph: SchemaGraph) -> list[Signal]:
    """Detect signals indicating a lookup/reference table."""
    signals: list[Signal] = []

    # Signal: Very few columns (typically id, code, name/description)
    if len(table.columns) <= 4:
        signals.append(Signal(
            name="narrow_table",
            description=f"Table has only {len(table.columns)} columns (lookup pattern)",
            signal_type=SignalType.STRUCTURAL,
            weight=0.6,
        ))

    # Signal: Lookup naming patterns
    lookup_patterns = {
        "lookup", "type", "types", "status", "statuses", "category", "categories",
        "code", "codes", "enum", "reference", "ref",
    }
    if any(p in table.name.lower() for p in lookup_patterns):
        signals.append(Signal(
            name="lookup_table_name",
            description=f"Table name '{table.name}' suggests a lookup table",
            signal_type=SignalType.NAMING,
            weight=0.5,
        ))

    # Signal: Has code + description pattern
    col_names = {c.name.lower() for c in table.columns}
    has_code = any(n in col_names for n in {"code", "key", "value"})
    has_desc = any(n in col_names for n in {"name", "description", "label", "title"})
    if has_code and has_desc:
        signals.append(Signal(
            name="code_description_pattern",
            description="Has code + description column pattern",
            signal_type=SignalType.NAMING,
            weight=0.5,
        ))

    # Signal: No foreign keys (pure reference data)
    if len(table.foreign_keys) == 0:
        signals.append(Signal(
            name="no_dependencies",
            description="Table has no foreign keys (independent reference data)",
            signal_type=SignalType.STRUCTURAL,
            weight=0.4,
        ))

    # Signal: Small estimated row count
    if table.row_estimate is not None and table.row_estimate < 100:
        signals.append(Signal(
            name="low_cardinality",
            description=f"Table has ~{table.row_estimate} rows (low cardinality)",
            signal_type=SignalType.CARDINALITY,
            weight=0.5,
        ))

    return signals


# =============================================================================
# Role Detector
# =============================================================================


# Type for signal detector functions
SignalDetector = Callable[[Table, SchemaGraph], list[Signal]]


# Registry of role detectors with their associated role
_ROLE_DETECTORS: list[tuple[RoleType, SignalDetector]] = [
    (RoleType.JUNCTION, _detect_junction_signals),
    (RoleType.SCD_TYPE_2, _detect_scd_type2_signals),
    (RoleType.EVENT, _detect_event_signals),
    (RoleType.FACT, _detect_fact_signals),
    (RoleType.DIMENSION, _detect_dimension_signals),
    (RoleType.LOOKUP, _detect_lookup_signals),
]


class RoleDetector:
    """
    Detects the semantic role of database tables.
    
    Uses signal-based heuristics to infer whether a table is a
    fact table, dimension, event log, junction table, etc.
    
    Example:
        >>> detector = RoleDetector()
        >>> result = detector.detect(orders_table, schema_graph)
        >>> print(result.summary())
        public.orders: FACT (85%)
    """

    def __init__(
        self,
        min_confidence: float = 0.3,
        role_detectors: list[tuple[RoleType, SignalDetector]] | None = None,
    ) -> None:
        """
        Initialize the role detector.
        
        Args:
            min_confidence: Minimum confidence to report a role (default 0.3).
            role_detectors: Custom role detectors to use. If None, uses defaults.
        """
        self.min_confidence = min_confidence
        self._detectors = _ROLE_DETECTORS if role_detectors is None else role_detectors

    def detect(self, table: Table, graph: SchemaGraph) -> TableRoleResult:
        """
        Detect the role of a single table.
        
        Args:
            table: Table to analyze.
            graph: Full schema graph for context.
        
        Returns:
            TableRoleResult with role hypothesis, confidence, and signals.
        """
        # Collect signals for each role
        role_signals: dict[RoleType, list[Signal]] = {}
        role_scores: dict[RoleType, float] = {}

        for role, detector in self._detectors:
            signals = detector(table, graph)
            if signals:
                role_signals[role] = signals
                # Score is sum of weights, normalized to max 1.0
                total_weight = sum(s.weight for s in signals)
                # Apply diminishing returns for many weak signals
                role_scores[role] = min(1.0, total_weight * 0.8)

        # If no signals detected, return UNKNOWN
        if not role_scores:
            return TableRoleResult(
                table=table.fqn,
                primary_role=RoleType.UNKNOWN,
                confidence=0.0,
                signals=[],
                alternatives=[],
            )

        # Sort roles by score
        sorted_roles = sorted(
            role_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # Primary role is the highest scoring
        primary_role, primary_score = sorted_roles[0]

        # Alternatives are other roles above min_confidence
        alternatives = [
            (role, score)
            for role, score in sorted_roles[1:]
            if score >= self.min_confidence
        ]

        return TableRoleResult(
            table=table.fqn,
            primary_role=primary_role,
            confidence=primary_score,
            signals=role_signals.get(primary_role, []),
            alternatives=alternatives,
        )

    def detect_all(self, graph: SchemaGraph) -> dict[str, TableRoleResult]:
        """
        Detect roles for all tables in a schema graph.
        
        Args:
            graph: Schema graph to analyze.
        
        Returns:
            Dictionary mapping table FQN to role results.
        """
        return {
            table.fqn: self.detect(table, graph)
            for table in graph
        }

    def detect_with_validation(
        self,
        table: Table,
        graph: SchemaGraph,
    ) -> TableRoleResult:
        """
        Detect role with cross-validation against related tables.
        
        This method checks for consistency between a table's role
        and the roles of tables it references or is referenced by.
        
        Args:
            table: Table to analyze.
            graph: Full schema graph for context.
        
        Returns:
            TableRoleResult with potentially adjusted confidence.
        """
        result = self.detect(table, graph)

        # Cross-validate based on relationships
        # If we think it's a FACT, check that it references DIMENSIONs
        if result.primary_role == RoleType.FACT:
            referenced = graph.tables_referenced_by(table.fqn)
            dim_count = sum(
                1 for t in referenced
                if self.detect(t, graph).primary_role in (RoleType.DIMENSION, RoleType.LOOKUP)
            )
            if referenced and dim_count >= len(referenced) * 0.5:
                # Boost confidence if most referenced tables are dimensions
                result.confidence = min(1.0, result.confidence * 1.1)
                result.signals.append(Signal(
                    name="references_dimensions",
                    description=f"References {dim_count} dimension/lookup tables",
                    signal_type=SignalType.CARDINALITY,
                    weight=0.2,
                ))

        return result
