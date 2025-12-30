"""
Abstract base classes and protocols for database introspection.

This module defines the contract that all database introspectors must follow.
New database engines can be supported by implementing the Introspector protocol.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from flaqes.core.schema_graph import SchemaGraph, Table


@dataclass(frozen=True, slots=True)
class IntrospectionConfig:
    """
    Configuration for schema introspection.

    Controls which schemas/tables to include and what metadata to extract.
    """

    schemas: tuple[str, ...] = ("public",)
    """Schemas to introspect. Order matters for priority."""

    include_tables: tuple[str, ...] | None = None
    """
    Specific tables to include (fully qualified or simple names).
    If None, all tables in the specified schemas are included.
    """

    exclude_tables: tuple[str, ...] = field(default_factory=tuple)
    """Tables to exclude (glob patterns supported, e.g., 'pg_*')."""

    include_views: bool = False
    """Whether to include views in introspection."""

    include_materialized_views: bool = False
    """Whether to include materialized views."""

    include_partitions: bool = True
    """Whether to include partitioned tables and their partitions."""

    include_row_estimates: bool = True
    """Whether to fetch row count estimates from statistics."""

    include_comments: bool = True
    """Whether to fetch table and column comments."""

    include_indexes: bool = True
    """Whether to fetch index information."""


@dataclass(frozen=True, slots=True)
class IntrospectionResult:
    """
    Result of a database introspection operation.

    Contains the schema graph and metadata about the introspection process.
    """

    graph: SchemaGraph
    """The extracted schema graph."""

    engine: str
    """Database engine identifier (e.g., 'postgresql', 'mysql')."""

    engine_version: str | None = None
    """Database engine version string."""

    introspected_schemas: tuple[str, ...] = field(default_factory=tuple)
    """Schemas that were actually introspected."""

    table_count: int = 0
    """Number of tables introspected."""

    relationship_count: int = 0
    """Number of relationships discovered."""

    warnings: tuple[str, ...] = field(default_factory=tuple)
    """Any warnings encountered during introspection."""

    @property
    def summary(self) -> str:
        """Return a human-readable summary of the introspection result."""
        return (
            f"{self.engine} ({self.engine_version or 'unknown version'}): "
            f"{self.table_count} tables, {self.relationship_count} relationships"
        )


@runtime_checkable
class IntrospectorProtocol(Protocol):
    """
    Protocol defining the interface for database introspectors.

    All database-specific introspectors must implement this protocol.
    Using Protocol allows for duck typing while maintaining type safety.
    """

    @property
    def engine(self) -> str:
        """
        Return the engine identifier.

        This should match the Engine literal type (e.g., 'postgresql').
        """
        ...

    async def introspect(
        self,
        config: IntrospectionConfig | None = None,
    ) -> IntrospectionResult:
        """
        Introspect the database and return a schema graph.

        Args:
            config: Configuration controlling what to introspect.
                   If None, uses default configuration.

        Returns:
            IntrospectionResult containing the schema graph and metadata.

        Raises:
            ConnectionError: If unable to connect to the database.
            IntrospectionError: If introspection fails.
        """
        ...

    async def introspect_table(
        self,
        table_name: str,
        schema: str | None = None,
    ) -> Table | None:
        """
        Introspect a single table.

        Args:
            table_name: Name of the table to introspect.
            schema: Schema containing the table. If None, uses default schema.

        Returns:
            Table object if found, None otherwise.
        """
        ...

    async def close(self) -> None:
        """
        Close any open connections.

        Should be called when done with introspection.
        """
        ...


class Introspector(ABC):
    """
    Abstract base class for database introspectors.

    Provides common functionality and defines the contract for
    database-specific implementations.

    Subclasses must implement:
    - engine property
    - _connect() method
    - _introspect_tables() method
    - _introspect_columns() method
    - _introspect_constraints() method
    - _introspect_indexes() method
    """

    def __init__(self, dsn: str) -> None:
        """
        Initialize the introspector with a connection string.

        Args:
            dsn: Database connection string (engine-specific format).
        """
        self._dsn = dsn
        self._connected = False

    @property
    @abstractmethod
    def engine(self) -> str:
        """Return the engine identifier."""
        ...

    @abstractmethod
    async def _connect(self) -> None:
        """Establish connection to the database."""
        ...

    @abstractmethod
    async def _get_engine_version(self) -> str | None:
        """Get the database engine version."""
        ...

    @abstractmethod
    async def _introspect_tables(
        self,
        config: IntrospectionConfig,
    ) -> list[Table]:
        """
        Introspect all tables matching the configuration.

        This should populate basic table info and columns.
        """
        ...

    @abstractmethod
    async def _introspect_constraints(
        self,
        tables: list[Table],
        config: IntrospectionConfig,
    ) -> None:
        """
        Introspect constraints for the given tables.

        This should populate primary keys, foreign keys, and other constraints.
        Modifies tables in place.
        """
        ...

    @abstractmethod
    async def _introspect_indexes(
        self,
        tables: list[Table],
        config: IntrospectionConfig,
    ) -> None:
        """
        Introspect indexes for the given tables.

        Modifies tables in place.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close database connection."""
        ...

    async def introspect(
        self,
        config: IntrospectionConfig | None = None,
    ) -> IntrospectionResult:
        """
        Introspect the database and return a schema graph.

        This is the main entry point for introspection.
        """
        if config is None:
            config = IntrospectionConfig()

        # Ensure we're connected
        if not self._connected:
            await self._connect()

        # Get engine version
        engine_version = await self._get_engine_version()

        # Introspect tables with columns
        tables = await self._introspect_tables(config)

        # Add constraints (PK, FK, etc.)
        await self._introspect_constraints(tables, config)

        # Add indexes
        if config.include_indexes:
            await self._introspect_indexes(tables, config)

        # Build the graph
        graph = SchemaGraph.from_tables(tables)

        return IntrospectionResult(
            graph=graph,
            engine=self.engine,
            engine_version=engine_version,
            introspected_schemas=config.schemas,
            table_count=len(tables),
            relationship_count=len(graph.relationships),
        )

    async def introspect_table(
        self,
        table_name: str,
        schema: str | None = None,
    ) -> Table | None:
        """Introspect a single table."""
        if schema is None:
            schema = "public"

        config = IntrospectionConfig(
            schemas=(schema,),
            include_tables=(f"{schema}.{table_name}",),
        )

        result = await self.introspect(config)
        return result.graph.get_table_by_name(table_name, schema)

    async def __aenter__(self) -> "Introspector":
        """Async context manager entry."""
        await self._connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Async context manager exit."""
        await self.close()


class IntrospectionError(Exception):
    """Raised when introspection fails."""

    def __init__(self, message: str, engine: str, cause: Exception | None = None):
        super().__init__(message)
        self.engine = engine
        self.cause = cause
