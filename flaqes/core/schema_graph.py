"""
Schema graph data structures.

These dataclasses represent the raw structural facts extracted from
a database catalog. They are deterministic and objective — no inference
or interpretation happens at this layer.
"""

from dataclasses import dataclass, field
from typing import Self

from flaqes.core.types import (
    Cardinality,
    ConstraintType,
    DataTypeCategory,
    IndexMethod,
)

# =============================================================================
# Column & Data Type
# =============================================================================


@dataclass(frozen=True, slots=True)
class DataType:
    """
    Represents a column's data type with both raw and categorized forms.

    We keep the raw type string for exact matching and reporting,
    while the category enables pattern matching without caring about
    specific type variants.
    """

    raw: str
    """Raw type as reported by the database (e.g., 'character varying(255)')."""

    category: DataTypeCategory
    """High-level category for pattern matching."""

    is_array: bool = False
    """Whether this is an array type."""

    element_type: str | None = None
    """For arrays, the element type."""

    def __str__(self) -> str:
        return self.raw


@dataclass(frozen=True, slots=True)
class Column:
    """Represents a table column with its properties."""

    name: str
    """Column name."""

    data_type: DataType
    """Column data type."""

    nullable: bool = True
    """Whether the column allows NULL values."""

    default: str | None = None
    """Default value expression, if any."""

    is_generated: bool = False
    """Whether this is a generated/computed column."""

    is_identity: bool = False
    """Whether this is an identity column (auto-increment)."""

    comment: str | None = None
    """Column comment/description from the database."""

    ordinal_position: int = 0
    """Column position in table (1-indexed)."""

    def __str__(self) -> str:
        nullable_str = "" if self.nullable else " NOT NULL"
        return f"{self.name} {self.data_type}{nullable_str}"


# =============================================================================
# Keys & Constraints
# =============================================================================


@dataclass(frozen=True, slots=True)
class PrimaryKey:
    """Represents a table's primary key."""

    name: str | None
    """Constraint name, if named."""

    columns: tuple[str, ...]
    """Column names in the primary key, in order."""

    @property
    def is_composite(self) -> bool:
        """Check if this is a composite primary key."""
        return len(self.columns) > 1


@dataclass(frozen=True, slots=True)
class ForeignKey:
    """Represents a foreign key relationship."""

    name: str | None
    """Constraint name, if named."""

    columns: tuple[str, ...]
    """Local column names in the foreign key."""

    target_schema: str
    """Schema of the referenced table."""

    target_table: str
    """Name of the referenced table."""

    target_columns: tuple[str, ...]
    """Column names in the referenced table."""

    on_delete: str = "NO ACTION"
    """ON DELETE action (CASCADE, SET NULL, etc.)."""

    on_update: str = "NO ACTION"
    """ON UPDATE action."""

    @property
    def is_composite(self) -> bool:
        """Check if this is a composite foreign key."""
        return len(self.columns) > 1

    @property
    def target_fqn(self) -> str:
        """Fully qualified name of target table."""
        return f"{self.target_schema}.{self.target_table}"


@dataclass(frozen=True, slots=True)
class Constraint:
    """Represents a table constraint (other than PK/FK)."""

    name: str | None
    """Constraint name, if named."""

    constraint_type: ConstraintType
    """Type of constraint."""

    columns: tuple[str, ...] = field(default_factory=tuple)
    """Columns involved in the constraint."""

    expression: str | None = None
    """For CHECK constraints, the check expression."""


# =============================================================================
# Indexes
# =============================================================================


@dataclass(frozen=True, slots=True)
class Index:
    """Represents a database index."""

    name: str
    """Index name."""

    table_schema: str
    """Schema containing the indexed table."""

    table_name: str
    """Name of the indexed table."""

    columns: tuple[str, ...]
    """Indexed columns, in order."""

    method: IndexMethod = IndexMethod.BTREE
    """Index access method."""

    is_unique: bool = False
    """Whether this is a unique index."""

    is_primary: bool = False
    """Whether this index backs the primary key."""

    is_partial: bool = False
    """Whether this is a partial (filtered) index."""

    predicate: str | None = None
    """For partial indexes, the WHERE clause."""

    expression_columns: tuple[str, ...] = field(default_factory=tuple)
    """For expression indexes, the expressions used."""

    @property
    def is_expression_index(self) -> bool:
        """Check if this index uses expressions."""
        return len(self.expression_columns) > 0


# =============================================================================
# Table
# =============================================================================


@dataclass(slots=True)
class Table:
    """
    Represents a database table with all its structural components.

    This is the central unit of analysis in flaqes. All pattern
    detection and tension analysis operates on Table instances.
    """

    name: str
    """Table name."""

    schema: str = "public"
    """Schema containing the table."""

    columns: list[Column] = field(default_factory=list)
    """Columns in the table, ordered by position."""

    primary_key: PrimaryKey | None = None
    """Primary key constraint, if any."""

    foreign_keys: list[ForeignKey] = field(default_factory=list)
    """Foreign key constraints."""

    constraints: list[Constraint] = field(default_factory=list)
    """Other constraints (unique, check, exclusion)."""

    indexes: list[Index] = field(default_factory=list)
    """Indexes on this table."""

    comment: str | None = None
    """Table comment/description from the database."""

    row_estimate: int | None = None
    """Estimated row count from pg_stat, if available."""

    @property
    def fqn(self) -> str:
        """Fully qualified table name."""
        return f"{self.schema}.{self.name}"

    @property
    def column_names(self) -> list[str]:
        """List of column names."""
        return [c.name for c in self.columns]

    def get_column(self, name: str) -> Column | None:
        """Get a column by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def has_column(self, name: str) -> bool:
        """Check if table has a column with given name."""
        return any(c.name == name for c in self.columns)

    def columns_by_category(self, category: DataTypeCategory) -> list[Column]:
        """Get columns matching a data type category."""
        return [c for c in self.columns if c.data_type.category == category]

    @property
    def timestamp_columns(self) -> list[Column]:
        """Get all timestamp/datetime columns."""
        return self.columns_by_category(DataTypeCategory.TIMESTAMP)

    @property
    def json_columns(self) -> list[Column]:
        """Get all JSON/JSONB columns."""
        return self.columns_by_category(DataTypeCategory.JSON)

    @property
    def has_surrogate_key(self) -> bool:
        """Check if table has a single-column auto-generated primary key."""
        if not self.primary_key or self.primary_key.is_composite:
            return False
        pk_col = self.get_column(self.primary_key.columns[0])
        return pk_col is not None and (pk_col.is_identity or pk_col.is_generated)

    @property
    def has_natural_key(self) -> bool:
        """Check if primary key appears to be a natural/business key."""
        if not self.primary_key:
            return False
        # Composite keys or non-auto-generated single keys suggest natural key
        if self.primary_key.is_composite:
            return True
        pk_col = self.get_column(self.primary_key.columns[0])
        return pk_col is not None and not pk_col.is_identity and not pk_col.is_generated


# =============================================================================
# Relationships
# =============================================================================


@dataclass(frozen=True, slots=True)
class Relationship:
    """
    Represents a relationship between two tables.

    Derived from foreign keys but enriched with cardinality
    and identifying relationship status.
    """

    source_table: str
    """Fully qualified name of the source (FK) table."""

    target_table: str
    """Fully qualified name of the target (PK) table."""

    foreign_key: ForeignKey
    """The foreign key constraint backing this relationship."""

    cardinality: Cardinality
    """Inferred cardinality of the relationship."""

    is_identifying: bool = False
    """Whether the FK is part of the source table's PK (identifying relationship)."""


# =============================================================================
# Schema Graph
# =============================================================================


@dataclass(slots=True)
class SchemaGraph:
    """
    Complete schema graph representing a database's structure.

    This is the primary input to flaqes' analysis pipeline.
    It contains all tables, relationships, and structural facts
    extracted from database introspection.
    """

    tables: dict[str, Table] = field(default_factory=dict)
    """Tables indexed by fully qualified name (schema.table)."""

    relationships: list[Relationship] = field(default_factory=list)
    """All relationships between tables."""

    def add_table(self, table: Table) -> None:
        """Add a table to the graph."""
        self.tables[table.fqn] = table

    def get_table(self, fqn: str) -> Table | None:
        """Get a table by fully qualified name."""
        return self.tables.get(fqn)

    def get_table_by_name(self, name: str, schema: str = "public") -> Table | None:
        """Get a table by name and optional schema."""
        return self.tables.get(f"{schema}.{name}")

    def tables_referencing(self, table_fqn: str) -> list[Table]:
        """Get all tables that have foreign keys pointing to the given table."""
        result = []
        for rel in self.relationships:
            if rel.target_table == table_fqn:
                source = self.get_table(rel.source_table)
                if source:
                    result.append(source)
        return result

    def tables_referenced_by(self, table_fqn: str) -> list[Table]:
        """Get all tables that the given table references via foreign keys."""
        result = []
        for rel in self.relationships:
            if rel.source_table == table_fqn:
                target = self.get_table(rel.target_table)
                if target:
                    result.append(target)
        return result

    def neighborhood(self, table_fqn: str, depth: int = 1) -> set[str]:
        """
        Get the neighborhood of a table up to a given FK depth.

        Returns fully qualified names of all tables within `depth` FK hops.
        """
        visited: set[str] = {table_fqn}
        frontier = {table_fqn}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for fqn in frontier:
                for rel in self.relationships:
                    if rel.source_table == fqn and rel.target_table not in visited:
                        next_frontier.add(rel.target_table)
                        visited.add(rel.target_table)
                    if rel.target_table == fqn and rel.source_table not in visited:
                        next_frontier.add(rel.source_table)
                        visited.add(rel.source_table)
            frontier = next_frontier

        return visited

    @classmethod
    def from_tables(cls, tables: list[Table]) -> Self:
        """
        Create a SchemaGraph from a list of tables.

        Relationships are inferred from foreign keys.
        """
        graph = cls()
        for table in tables:
            graph.add_table(table)

        # Build relationships from foreign keys
        for table in tables:
            for fk in table.foreign_keys:
                target_fqn = fk.target_fqn

                # Determine cardinality
                # If FK columns are unique, it's one-to-one; otherwise one-to-many
                is_unique_fk = any(
                    c.columns == fk.columns
                    for c in table.constraints
                    if c.constraint_type == ConstraintType.UNIQUE
                ) or (
                    table.primary_key is not None
                    and table.primary_key.columns == fk.columns
                )

                cardinality = (
                    Cardinality.ONE_TO_ONE if is_unique_fk else Cardinality.MANY_TO_ONE
                )

                # Check if FK is part of PK (identifying relationship)
                is_identifying = table.primary_key is not None and any(
                    col in table.primary_key.columns for col in fk.columns
                )

                graph.relationships.append(
                    Relationship(
                        source_table=table.fqn,
                        target_table=target_fqn,
                        foreign_key=fk,
                        cardinality=cardinality,
                        is_identifying=is_identifying,
                    )
                )

        return graph

    def __len__(self) -> int:
        """Number of tables in the graph."""
        return len(self.tables)

    def __iter__(self):
        """Iterate over tables."""
        return iter(self.tables.values())
