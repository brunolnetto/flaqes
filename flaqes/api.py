"""
Main API for flaqes schema analysis.

This module provides the primary entry point for analyzing database schemas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flaqes.core.intent import Intent
from flaqes.core.schema_graph import SchemaGraph
<<<<<<< HEAD
from flaqes.introspection import get_introspector_from_dsn
from flaqes.introspection.base import IntrospectionConfig
from flaqes.report import SchemaReport, generate_report

if TYPE_CHECKING:
    from flaqes.introspection.base import Introspector
=======
from flaqes.introspection.base import IntrospectionConfig
from flaqes.introspection.registry import get_introspector_from_dsn
from flaqes.report import SchemaReport, generate_report

if TYPE_CHECKING:
    pass
>>>>>>> 3874906 (feat(): Mermaid diagram)


async def analyze_schema(
    dsn: str,
    intent: Intent | None = None,
    tables: list[str] | None = None,
    schemas: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> SchemaReport:
    """
    Analyze a database schema and generate a comprehensive report.

    This is the main entry point for flaqes. It:
    1. Introspects the database to build a SchemaGraph
    2. Detects table roles (fact, dimension, event, etc.)
    3. Identifies design patterns (SCD, soft delete, etc.)
    4. Analyzes design tensions based on stated intent
    5. Generates a structured report

    Args:
        dsn: Database connection string (e.g., "postgresql://user:pass@host/db")
        intent: Optional Intent specifying workload characteristics.
                If not provided, default intent is used (less contextual advice).
        tables: Optional list of specific tables to analyze.
                If None, analyzes all tables.
        schemas: Optional list of schemas to include.
                 If None, uses default schema for the database.
        exclude_patterns: Optional list of patterns to exclude (e.g., ["tmp_*", "staging_*"])

    Returns:
        SchemaReport containing all analysis results, including:
        - Table roles with confidence scores
        - Detected design patterns
        - Design tensions with alternatives
        - Summary statistics

    Raises:
        IntrospectionError: If database connection or introspection fails
        ValueError: If intent is invalid

    Example:
        >>> import asyncio
        >>> from flaqes import analyze_schema, Intent
<<<<<<< HEAD
        >>> 
=======
        >>>
>>>>>>> 3874906 (feat(): Mermaid diagram)
        >>> async def main():
        ...     intent = Intent(
        ...         workload="OLAP",
        ...         write_frequency="low",
        ...         read_patterns=["aggregation", "range_scan"],
        ...         data_volume="large",
        ...     )
        ...
        ...     report = await analyze_schema(
        ...         dsn="postgresql://localhost/mydb",
        ...         intent=intent,
        ...     )
        ...
        ...     print(report.to_markdown())
        ...
        ... asyncio.run(main())
    """
    # Get the appropriate introspector for the DSN
<<<<<<< HEAD
    introspector: Introspector = get_introspector_from_dsn(dsn)
    
=======
    introspector = get_introspector_from_dsn(dsn)

>>>>>>> 3874906 (feat(): Mermaid diagram)
    # Configure introspection
    config = IntrospectionConfig(
        include_tables=tuple(tables) if tables else None,
        schemas=tuple(schemas) if schemas else ("public",),
        exclude_tables=tuple(exclude_patterns) if exclude_patterns else (),
    )

    # Connect and introspect
    async with introspector:
        result = await introspector.introspect(config)
<<<<<<< HEAD
    
    # Build schema graph from introspection result
    graph = result.graph
    
    # Generate and return report
    return generate_report(graph, intent=intent)
=======

    # Generate and return report using the introspected graph
    return generate_report(result.graph, intent=intent)
>>>>>>> 3874906 (feat(): Mermaid diagram)


async def introspect_schema(
    dsn: str,
    tables: list[str] | None = None,
    schemas: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> SchemaGraph:
    """
    Introspect a database and return the raw SchemaGraph.

    This is a lower-level API for users who want just the structural
    facts without analysis. Useful for:
    - Building custom analysis tools
    - Exporting schema metadata
    - Integration with other tools

    Args:
        dsn: Database connection string
        tables: Optional list of specific tables
        schemas: Optional list of schemas to include
        exclude_patterns: Optional list of patterns to exclude

    Returns:
        SchemaGraph containing all structural information

    Example:
        >>> graph = await introspect_schema("postgresql://localhost/mydb")
        >>> for table in graph:
        ...     print(f"{table.name}: {len(table.columns)} columns")
    """
<<<<<<< HEAD
    introspector: Introspector = get_introspector_from_dsn(dsn)
    
=======
    introspector = get_introspector_from_dsn(dsn)

>>>>>>> 3874906 (feat(): Mermaid diagram)
    config = IntrospectionConfig(
        include_tables=tuple(tables) if tables else None,
        schemas=tuple(schemas) if schemas else ("public",),
        exclude_tables=tuple(exclude_patterns) if exclude_patterns else (),
    )

    async with introspector:
        result = await introspector.introspect(config)

    return result.graph
