"""
Design tension analysis for database schemas.

This module detects potential design tensions in a database schema and provides:
- **Current Benefits**: Why the current design makes sense
- **Risks**: What could go wrong with the current design
- **Breaking Points**: When the design will start to cause problems
- **Alternatives**: What could be done differently, with trade-offs

Design tensions are intent-aware - severity depends on the stated workload.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import NamedTuple

from flakes.analysis.pattern_matcher import PatternDetector, PatternType
from flakes.analysis.role_detector import RoleDetector, RoleType
from flakes.core.intent import Intent
from flakes.core.schema_graph import SchemaGraph, Table
from flakes.core.types import DataTypeCategory, Severity, TensionCategory


# =============================================================================
# Effort Enum
# =============================================================================


class Effort(Enum):
    """Estimated effort to implement an alternative."""
    
    LOW = "low"  # Minutes to hours, simple change
    MEDIUM = "medium"  # Hours to days, moderate refactoring
    HIGH = "high"  # Days to weeks, significant migration


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class Alternative:
    """A proposed alternative to the current design."""
    
    description: str
    trade_off: str
    effort: Effort
    example_ddl: str | None = None
    
    def summary(self) -> str:
        """Return a formatted summary."""
        return f"{self.description} [Effort: {self.effort.value}]"


@dataclass
class DesignTension:
    """A detected design tension in the schema.
    
    A tension is not necessarily a problem - it's a trade-off
    that should be understood in context of the workload.
    """
    
    id: str
    category: TensionCategory
    description: str
    current_benefit: str
    risk: str
    breaking_point: str
    severity: Severity
    table: str  # Table FQN
    columns: tuple[str, ...] = ()
    alternatives: list[Alternative] = field(default_factory=list)
    
    @property
    def is_critical(self) -> bool:
        """Return True if this is a critical tension."""
        return self.severity == Severity.CRITICAL
    
    @property
    def is_warning(self) -> bool:
        """Return True if this is a warning-level tension."""
        return self.severity == Severity.WARNING
    
    def summary(self) -> str:
        """Return a formatted summary."""
        return f"[{self.severity.name}] {self.table}: {self.description}"


class TensionSignal(NamedTuple):
    """Evidence supporting a tension detection."""
    
    name: str
    description: str
    severity_weight: float  # 0.0 to 1.0, affects final severity


# =============================================================================
# Tension Detection Functions
# =============================================================================


def _detect_wide_table(table: Table, intent: Intent | None) -> DesignTension | None:
    """Detect wide table tension.
    
    Wide tables with many columns can cause:
    - Performance issues with SELECT *
    - Lock contention on updates
    - Memory pressure during scans
    """
    column_count = len(table.columns)
    
    # Thresholds based on intent
    if intent and intent.workload == "OLAP":
        # OLAP tolerates wider tables
        warning_threshold = 50
        critical_threshold = 100
    else:
        # OLTP prefers narrower tables
        warning_threshold = 30
        critical_threshold = 60
    
    if column_count < warning_threshold:
        return None
    
    severity = Severity.CRITICAL if column_count >= critical_threshold else Severity.WARNING
    
    return DesignTension(
        id="wide_table",
        category=TensionCategory.PERFORMANCE,
        description=f"Table has {column_count} columns",
        current_benefit="All related data in one table, simple queries",
        risk="SELECT * fetches unused data, row locks affect many columns",
        breaking_point=f"When row size exceeds ~8KB or column count > {critical_threshold}",
        severity=severity,
        table=table.fqn,
        alternatives=[
            Alternative(
                description="Split into normalized tables",
                trade_off="More JOINs required, increased query complexity",
                effort=Effort.HIGH,
                example_ddl=f"-- Move rarely-used columns to {table.name}_details table",
            ),
            Alternative(
                description="Use JSONB for flexible attributes",
                trade_off="Harder to query/index, schema flexibility vs structure",
                effort=Effort.MEDIUM,
                example_ddl=f"ALTER TABLE {table.name} ADD COLUMN extra_attributes JSONB;",
            ),
        ],
    )


def _detect_missing_indexes(
    table: Table,
    relations: list,
    intent: Intent | None,
) -> list[DesignTension]:
    """Detect missing indexes on foreign key columns.
    
    FK columns without indexes cause:
    - Slow JOIN performance
    - Table scans on DELETE of parent records
    """
    tensions: list[DesignTension] = []
    
    # Get indexed column sets
    indexed_columns = set()
    for idx in table.indexes:
        if idx.columns:
            # First column of an index is what matters for simple lookups
            indexed_columns.add(idx.columns[0])
    
    # Check each FK column
    for fk in table.foreign_keys:
        for col in fk.columns:
            if col not in indexed_columns:
                severity = Severity.WARNING
                if intent and intent.workload == "OLTP":
                    severity = Severity.CRITICAL
                
                tensions.append(DesignTension(
                    id=f"missing_fk_index_{col}",
                    category=TensionCategory.PERFORMANCE,
                    description=f"Foreign key column '{col}' lacks an index",
                    current_benefit="Faster INSERTs without index maintenance",
                    risk="Slow JOINs and cascading DELETEs cause table scans",
                    breaking_point="When table exceeds ~10K rows or JOINs become frequent",
                    severity=severity,
                    table=table.fqn,
                    columns=(col,),
                    alternatives=[
                        Alternative(
                            description=f"Add index on {col}",
                            trade_off="Slightly slower writes, more storage",
                            effort=Effort.LOW,
                            example_ddl=f"CREATE INDEX idx_{table.name}_{col} ON {table.fqn} ({col});",
                        ),
                    ],
                ))
    
    return tensions


def _detect_nullable_foreign_key(table: Table, intent: Intent | None) -> list[DesignTension]:
    """Detect nullable foreign keys.
    
    Nullable FKs can indicate:
    - Optional relationships (valid design)
    - Polymorphic association smell
    - Data quality issues
    """
    tensions: list[DesignTension] = []
    
    for fk in table.foreign_keys:
        for col_name in fk.columns:
            col = table.get_column(col_name)
            if col and col.nullable:
                tensions.append(DesignTension(
                    id=f"nullable_fk_{col_name}",
                    category=TensionCategory.CONSISTENCY,
                    description=f"Foreign key column '{col_name}' is nullable",
                    current_benefit="Allows optional relationships, flexible data entry",
                    risk="NULL references can mask data quality issues, JOIN complexity",
                    breaking_point="When NULL ratio exceeds ~20% or causes reporting errors",
                    severity=Severity.INFO,
                    table=table.fqn,
                    columns=(col_name,),
                    alternatives=[
                        Alternative(
                            description="Use a junction table for optional relationships",
                            trade_off="More tables, explicit modeling of relationship presence",
                            effort=Effort.MEDIUM,
                        ),
                        Alternative(
                            description="Add default 'unknown' reference row in target table",
                            trade_off="Requires managing sentinel values",
                            effort=Effort.LOW,
                        ),
                    ],
                ))
    
    return tensions


def _detect_jsonb_overuse(table: Table, intent: Intent | None) -> DesignTension | None:
    """Detect potential JSONB overuse.
    
    JSONB is great for flexibility but can indicate:
    - Schema avoidance
    - Difficulty querying/indexing
    - Lack of type safety
    """
    json_columns = [c for c in table.columns if c.data_type.category == DataTypeCategory.JSON]
    
    if not json_columns:
        return None
    
    # Count how much of the table is JSONB
    json_ratio = len(json_columns) / len(table.columns)
    
    if json_ratio < 0.3:
        return None  # Reasonable use of JSONB
    
    severity = Severity.WARNING
    if json_ratio > 0.5:
        severity = Severity.CRITICAL
    
    return DesignTension(
        id="jsonb_overuse",
        category=TensionCategory.EVOLUTION,
        description=f"{len(json_columns)} of {len(table.columns)} columns are JSON ({json_ratio:.0%})",
        current_benefit="Schema flexibility, rapid iteration, heterogeneous data",
        risk="No type safety, hard to query, index bloat, migration difficulties",
        breaking_point="When queries need specific JSON fields frequently",
        severity=severity,
        table=table.fqn,
        columns=tuple(c.name for c in json_columns),
        alternatives=[
            Alternative(
                description="Extract frequently-accessed fields to proper columns",
                trade_off="Requires migration, but improves query performance",
                effort=Effort.MEDIUM,
                example_ddl=f"-- Extract JSON fields to columns\n"
                           f"ALTER TABLE {table.fqn} ADD COLUMN extracted_field TEXT "
                           f"GENERATED ALWAYS AS (json_column->>'field') STORED;",
            ),
            Alternative(
                description="Add GIN index for JSON path queries",
                trade_off="Index maintenance overhead, storage cost",
                effort=Effort.LOW,
                example_ddl=f"CREATE INDEX idx_{table.name}_jsonb ON {table.fqn} "
                           f"USING GIN ({json_columns[0].name});",
            ),
        ],
    )


def _detect_missing_audit_columns(table: Table, intent: Intent | None) -> DesignTension | None:
    """Detect tables missing audit timestamp columns.
    
    Audit columns help with:
    - Debugging data issues
    - Compliance requirements
    - CDC/ETL patterns
    """
    col_names = {c.name.lower() for c in table.columns}
    
    has_created = any(n in col_names for n in {"created_at", "created_date", "create_time"})
    has_updated = any(n in col_names for n in {"updated_at", "modified_at", "update_time"})
    
    if has_created and has_updated:
        return None  # Has both
    
    missing = []
    if not has_created:
        missing.append("created_at")
    if not has_updated:
        missing.append("updated_at")
    
    return DesignTension(
        id="missing_audit_columns",
        category=TensionCategory.EVOLUTION,
        description=f"Missing audit columns: {', '.join(missing)}",
        current_benefit="Simpler schema, fewer columns to maintain",
        risk="Hard to track when data changed, compliance gaps, debugging difficulty",
        breaking_point="When auditing requirements emerge or debugging is needed",
        severity=Severity.INFO,
        table=table.fqn,
        alternatives=[
            Alternative(
                description="Add created_at/updated_at columns",
                trade_off="Small storage overhead, trigger or application logic needed",
                effort=Effort.LOW,
                example_ddl=f"ALTER TABLE {table.fqn} ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW();\n"
                           f"ALTER TABLE {table.fqn} ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();",
            ),
        ],
    )


def _detect_no_primary_key(table: Table, intent: Intent | None) -> DesignTension | None:
    """Detect tables without primary keys.
    
    Tables without PKs can cause:
    - No reliable row identity
    - ORM issues
    - Replication problems
    """
    if table.primary_key:
        return None
    
    return DesignTension(
        id="no_primary_key",
        category=TensionCategory.CONSISTENCY,
        description="Table has no primary key",
        current_benefit="Flexible data insertion, possible staging/log table",
        risk="No row identity, duplicates possible, ORM incompatibility, replication issues",
        breaking_point="When you need to UPDATE or DELETE specific rows",
        severity=Severity.CRITICAL,
        table=table.fqn,
        alternatives=[
            Alternative(
                description="Add surrogate key (SERIAL/BIGSERIAL)",
                trade_off="Additional column, auto-increment index",
                effort=Effort.LOW,
                example_ddl=f"ALTER TABLE {table.fqn} ADD COLUMN id BIGSERIAL PRIMARY KEY;",
            ),
            Alternative(
                description="Add natural key based on business identifiers",
                trade_off="Requires identifying unique business key combination",
                effort=Effort.MEDIUM,
            ),
        ],
    )


def _detect_text_without_constraint(table: Table, intent: Intent | None) -> list[DesignTension]:
    """Detect unbounded TEXT columns that might benefit from constraints.
    
    Unbounded text can cause:
    - Storage bloat
    - UI/API issues with unexpected lengths
    """
    tensions: list[DesignTension] = []
    
    for col in table.columns:
        if col.data_type.category == DataTypeCategory.TEXT:
            # Check if it's unbounded (no VARCHAR length)
            raw = col.data_type.raw.lower()
            if raw == "text" or raw == "character varying":
                tensions.append(DesignTension(
                    id=f"unbounded_text_{col.name}",
                    category=TensionCategory.CONSISTENCY,
                    description=f"Column '{col.name}' is unbounded TEXT",
                    current_benefit="No length restrictions, maximum flexibility",
                    risk="Storage bloat, unexpected data sizes, API/UI issues",
                    breaking_point="When large text values cause memory or display issues",
                    severity=Severity.INFO,
                    table=table.fqn,
                    columns=(col.name,),
                    alternatives=[
                        Alternative(
                            description=f"Add CHECK constraint for reasonable length",
                            trade_off="Requires determining appropriate limit",
                            effort=Effort.LOW,
                            example_ddl=f"ALTER TABLE {table.fqn} ADD CONSTRAINT "
                                       f"check_{col.name}_length CHECK (length({col.name}) <= 10000);",
                        ),
                    ],
                ))
    
    # Limit to first 3 to avoid noise
    return tensions[:3]


def _detect_denormalization(table: Table, graph: SchemaGraph, intent: Intent | None) -> list[DesignTension]:
    """Detect potential denormalization by looking for duplicate column patterns.
    
    Signs of denormalization:
    - Multiple columns with same suffix (_name, _email)
    - Columns that repeat data from referenced tables
    """
    tensions: list[DesignTension] = []
    col_names = [c.name.lower() for c in table.columns]
    
    # Look for repeated suffixes suggesting denormalized data
    name_cols = [n for n in col_names if n.endswith("_name") and n != "name"]
    email_cols = [n for n in col_names if n.endswith("_email")]
    
    denorm_hints = name_cols + email_cols
    
    if len(denorm_hints) >= 2:
        tensions.append(DesignTension(
            id="possible_denormalization",
            category=TensionCategory.NORMALIZATION,
            description=f"Multiple descriptive columns suggest denormalization: {', '.join(denorm_hints[:3])}",
            current_benefit="Faster reads without JOINs, useful for analytics",
            risk="Data inconsistency, update anomalies, storage overhead",
            breaking_point="When source data changes require multi-table updates",
            severity=Severity.INFO if intent and intent.workload == "OLAP" else Severity.WARNING,
            table=table.fqn,
            columns=tuple(denorm_hints[:3]),
            alternatives=[
                Alternative(
                    description="Normalize to separate tables with foreign keys",
                    trade_off="Requires JOINs, more complex queries",
                    effort=Effort.HIGH,
                ),
                Alternative(
                    description="Use materialized view for read-heavy denormalized access",
                    trade_off="Refresh overhead, eventual consistency",
                    effort=Effort.MEDIUM,
                    example_ddl=f"CREATE MATERIALIZED VIEW {table.name}_denorm AS SELECT ...;",
                ),
            ],
        ))
    
    return tensions


# =============================================================================
# Tension Analyzer Class
# =============================================================================


class TensionAnalyzer:
    """Analyze a schema for design tensions.
    
    Example:
        >>> analyzer = TensionAnalyzer(intent=Intent(...))
        >>> tensions = analyzer.analyze(graph)
        >>> for t in tensions:
        ...     print(t.summary())
    """
    
    def __init__(
        self,
        intent: Intent | None = None,
        min_severity: Severity = Severity.INFO,
    ) -> None:
        """Initialize the tension analyzer.
        
        Args:
            intent: The stated intent/workload. Affects severity scoring.
            min_severity: Minimum severity level to include in results.
        """
        self.intent = intent
        self.min_severity = min_severity
        self._role_detector = RoleDetector()
        self._pattern_detector = PatternDetector()
    
    def analyze_table(self, table: Table, graph: SchemaGraph) -> list[DesignTension]:
        """Analyze a single table for design tensions.
        
        Args:
            table: The table to analyze.
            graph: The full schema graph for context.
        
        Returns:
            List of detected tensions for this table.
        """
        tensions: list[DesignTension] = []
        
        # Get relationships for context
        relations = list(graph.relationships)
        
        # Run all tension detectors
        tension = _detect_wide_table(table, self.intent)
        if tension:
            tensions.append(tension)
        
        tensions.extend(_detect_missing_indexes(table, relations, self.intent))
        tensions.extend(_detect_nullable_foreign_key(table, self.intent))
        
        tension = _detect_jsonb_overuse(table, self.intent)
        if tension:
            tensions.append(tension)
        
        tension = _detect_missing_audit_columns(table, self.intent)
        if tension:
            tensions.append(tension)
        
        tension = _detect_no_primary_key(table, self.intent)
        if tension:
            tensions.append(tension)
        
        tensions.extend(_detect_text_without_constraint(table, self.intent))
        tensions.extend(_detect_denormalization(table, graph, self.intent))
        
        # Filter by minimum severity
        severity_order = [Severity.INFO, Severity.WARNING, Severity.CRITICAL]
        min_index = severity_order.index(self.min_severity)
        
        filtered = [
            t for t in tensions
            if severity_order.index(t.severity) >= min_index
        ]
        
        return filtered
    
    def analyze(self, graph: SchemaGraph) -> dict[str, list[DesignTension]]:
        """Analyze all tables in a schema for design tensions.
        
        Args:
            graph: The schema graph to analyze.
        
        Returns:
            Dictionary mapping table FQN to list of detected tensions.
        """
        results: dict[str, list[DesignTension]] = {}
        
        for table in graph:
            tensions = self.analyze_table(table, graph)
            if tensions:
                results[table.fqn] = tensions
        
        return results
    
    def get_summary(self, graph: SchemaGraph) -> dict[str, int]:
        """Get a summary of tension counts by category.
        
        Args:
            graph: The schema graph to analyze.
        
        Returns:
            Dictionary with counts by category and severity.
        """
        all_tensions = self.analyze(graph)
        
        summary = {
            "total": 0,
            "critical": 0,
            "warning": 0,
            "info": 0,
            "normalization": 0,
            "performance": 0,
            "evolution": 0,
            "consistency": 0,
        }
        
        for tensions in all_tensions.values():
            for t in tensions:
                summary["total"] += 1
                summary[t.severity.name.lower()] += 1
                summary[t.category.name.lower()] += 1
        
        return summary
