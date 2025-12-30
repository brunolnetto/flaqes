"""
PostgreSQL introspector implementation.

This module provides schema introspection for PostgreSQL databases
using asyncpg for async database access.
"""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING

import asyncpg

from flakes.core.schema_graph import (
    Column,
    Constraint,
    DataType,
    ForeignKey,
    Index,
    PrimaryKey,
    Table,
)
from flakes.core.types import ConstraintType, DataTypeCategory, IndexMethod
from flakes.introspection.base import (
    Introspector,
    IntrospectionConfig,
    IntrospectionError,
)
from flakes.introspection.registry import register_introspector

if TYPE_CHECKING:
    from asyncpg import Connection


# =============================================================================
# Type Mapping
# =============================================================================

# Map PostgreSQL type OIDs/names to our categories
_TYPE_CATEGORY_MAP: dict[str, DataTypeCategory] = {
    # Integer types
    "int2": DataTypeCategory.INTEGER,
    "int4": DataTypeCategory.INTEGER,
    "int8": DataTypeCategory.INTEGER,
    "smallint": DataTypeCategory.INTEGER,
    "integer": DataTypeCategory.INTEGER,
    "bigint": DataTypeCategory.INTEGER,
    "smallserial": DataTypeCategory.INTEGER,
    "serial": DataTypeCategory.INTEGER,
    "bigserial": DataTypeCategory.INTEGER,
    # Float types
    "float4": DataTypeCategory.FLOAT,
    "float8": DataTypeCategory.FLOAT,
    "real": DataTypeCategory.FLOAT,
    "double precision": DataTypeCategory.FLOAT,
    # Decimal types
    "numeric": DataTypeCategory.DECIMAL,
    "decimal": DataTypeCategory.DECIMAL,
    "money": DataTypeCategory.DECIMAL,
    # Text types
    "text": DataTypeCategory.TEXT,
    "varchar": DataTypeCategory.TEXT,
    "character varying": DataTypeCategory.TEXT,
    "char": DataTypeCategory.TEXT,
    "character": DataTypeCategory.TEXT,
    "bpchar": DataTypeCategory.TEXT,
    "name": DataTypeCategory.TEXT,
    # Boolean
    "bool": DataTypeCategory.BOOLEAN,
    "boolean": DataTypeCategory.BOOLEAN,
    # Timestamp types
    "timestamp": DataTypeCategory.TIMESTAMP,
    "timestamptz": DataTypeCategory.TIMESTAMP,
    "timestamp without time zone": DataTypeCategory.TIMESTAMP,
    "timestamp with time zone": DataTypeCategory.TIMESTAMP,
    # Date/Time
    "date": DataTypeCategory.DATE,
    "time": DataTypeCategory.TIME,
    "timetz": DataTypeCategory.TIME,
    "time without time zone": DataTypeCategory.TIME,
    "time with time zone": DataTypeCategory.TIME,
    "interval": DataTypeCategory.INTERVAL,
    # UUID
    "uuid": DataTypeCategory.UUID,
    # JSON
    "json": DataTypeCategory.JSON,
    "jsonb": DataTypeCategory.JSON,
    # Binary
    "bytea": DataTypeCategory.BINARY,
    # Arrays (handled specially)
    # Range types
    "int4range": DataTypeCategory.RANGE,
    "int8range": DataTypeCategory.RANGE,
    "numrange": DataTypeCategory.RANGE,
    "tsrange": DataTypeCategory.RANGE,
    "tstzrange": DataTypeCategory.RANGE,
    "daterange": DataTypeCategory.RANGE,
    # Geometric types
    "point": DataTypeCategory.GEOMETRIC,
    "line": DataTypeCategory.GEOMETRIC,
    "lseg": DataTypeCategory.GEOMETRIC,
    "box": DataTypeCategory.GEOMETRIC,
    "path": DataTypeCategory.GEOMETRIC,
    "polygon": DataTypeCategory.GEOMETRIC,
    "circle": DataTypeCategory.GEOMETRIC,
    # Network types
    "inet": DataTypeCategory.NETWORK,
    "cidr": DataTypeCategory.NETWORK,
    "macaddr": DataTypeCategory.NETWORK,
    "macaddr8": DataTypeCategory.NETWORK,
}


def _categorize_type(type_name: str) -> tuple[DataTypeCategory, bool, str | None]:
    """
    Categorize a PostgreSQL type name.
    
    Returns:
        Tuple of (category, is_array, element_type)
    """
    # Normalize type name
    type_lower = type_name.lower().strip()
    
    # Check for array types
    if type_lower.endswith("[]"):
        element_type = type_lower[:-2]
        element_category = _TYPE_CATEGORY_MAP.get(element_type, DataTypeCategory.OTHER)
        return DataTypeCategory.ARRAY, True, element_type
    
    # Check for array notation with underscore prefix
    if type_lower.startswith("_"):
        element_type = type_lower[1:]
        return DataTypeCategory.ARRAY, True, element_type
    
    # Look up in category map
    category = _TYPE_CATEGORY_MAP.get(type_lower, DataTypeCategory.OTHER)
    return category, False, None


def _map_index_method(method: str) -> IndexMethod:
    """Map PostgreSQL index method name to IndexMethod enum."""
    method_map = {
        "btree": IndexMethod.BTREE,
        "hash": IndexMethod.HASH,
        "gin": IndexMethod.GIN,
        "gist": IndexMethod.GIST,
        "spgist": IndexMethod.SPGIST,
        "brin": IndexMethod.BRIN,
    }
    return method_map.get(method.lower(), IndexMethod.BTREE)


# =============================================================================
# SQL Queries
# =============================================================================

# Query to get all tables
_TABLES_QUERY = """
SELECT 
    c.relname AS table_name,
    n.nspname AS schema_name,
    obj_description(c.oid) AS table_comment,
    c.reltuples::bigint AS row_estimate
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = ANY($1::text[])
  AND c.relkind = ANY($2::char[])
  AND NOT c.relispartition
ORDER BY n.nspname, c.relname
"""

# Query to get columns for tables
_COLUMNS_QUERY = """
SELECT 
    n.nspname || '.' || c.relname AS table_fqn,
    a.attname AS column_name,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
    t.typname AS type_name,
    a.attnotnull AS not_null,
    pg_get_expr(d.adbin, d.adrelid) AS default_value,
    a.attidentity != '' AS is_identity,
    a.attgenerated != '' AS is_generated,
    col_description(a.attrelid, a.attnum) AS column_comment,
    a.attnum AS ordinal_position
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_type t ON t.oid = a.atttypid
LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
WHERE n.nspname = ANY($1::text[])
  AND c.relkind = ANY($2::char[])
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY a.attrelid, a.attnum
"""

# Query to get primary keys
_PRIMARY_KEYS_QUERY = """
SELECT 
    n.nspname || '.' || cl.relname AS table_fqn,
    c.conname AS constraint_name,
    array_agg(a.attname ORDER BY array_position(c.conkey, a.attnum)) AS columns
FROM pg_constraint c
JOIN pg_class cl ON cl.oid = c.conrelid
JOIN pg_namespace n ON n.oid = cl.relnamespace
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
WHERE n.nspname = ANY($1::text[])
  AND c.contype = 'p'
GROUP BY n.nspname, cl.relname, c.conname
"""

# Query to get foreign keys
_FOREIGN_KEYS_QUERY = """
SELECT 
    n.nspname || '.' || cl.relname AS source_table,
    c.conname AS constraint_name,
    array_agg(DISTINCT a.attname ORDER BY a.attname) AS source_columns,
    nt.nspname || '.' || clt.relname AS target_table,
    array_agg(DISTINCT af.attname ORDER BY af.attname) AS target_columns,
    c.confupdtype AS on_update,
    c.confdeltype AS on_delete
FROM pg_constraint c
JOIN pg_class cl ON cl.oid = c.conrelid
JOIN pg_namespace n ON n.oid = cl.relnamespace
JOIN pg_class clt ON clt.oid = c.confrelid
JOIN pg_namespace nt ON nt.oid = clt.relnamespace
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
JOIN pg_attribute af ON af.attrelid = c.confrelid AND af.attnum = ANY(c.confkey)
WHERE n.nspname = ANY($1::text[])
  AND c.contype = 'f'
GROUP BY n.nspname, cl.relname, c.conname, nt.nspname, clt.relname, c.confupdtype, c.confdeltype
"""

# Query to get unique constraints
_UNIQUE_CONSTRAINTS_QUERY = """
SELECT 
    n.nspname || '.' || cl.relname AS table_fqn,
    c.conname AS constraint_name,
    array_agg(a.attname ORDER BY array_position(c.conkey, a.attnum)) AS columns
FROM pg_constraint c
JOIN pg_class cl ON cl.oid = c.conrelid
JOIN pg_namespace n ON n.oid = cl.relnamespace
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
WHERE n.nspname = ANY($1::text[])
  AND c.contype = 'u'
GROUP BY n.nspname, cl.relname, c.conname
"""

# Query to get check constraints
_CHECK_CONSTRAINTS_QUERY = """
SELECT 
    n.nspname || '.' || cl.relname AS table_fqn,
    c.conname AS constraint_name,
    pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint c
JOIN pg_class cl ON cl.oid = c.conrelid
JOIN pg_namespace n ON n.oid = cl.relnamespace
WHERE n.nspname = ANY($1::text[])
  AND c.contype = 'c'
"""

# Query to get indexes
_INDEXES_QUERY = """
SELECT 
    n.nspname || '.' || tc.relname AS table_fqn,
    ic.relname AS index_name,
    am.amname AS index_method,
    i.indisunique AS is_unique,
    i.indisprimary AS is_primary,
    pg_get_expr(i.indpred, i.indrelid) AS predicate,
    array_agg(a.attname ORDER BY array_position(i.indkey::int[], a.attnum::int)) 
        FILTER (WHERE a.attname IS NOT NULL) AS columns,
    array_agg(pg_get_indexdef(i.indexrelid, k.n::integer, true) ORDER BY k.n) 
        FILTER (WHERE a.attname IS NULL) AS expressions
FROM pg_index i
JOIN pg_class ic ON ic.oid = i.indexrelid
JOIN pg_class tc ON tc.oid = i.indrelid
JOIN pg_namespace n ON n.oid = tc.relnamespace
JOIN pg_am am ON am.oid = ic.relam
CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, n)
LEFT JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum AND k.attnum != 0
WHERE n.nspname = ANY($1::text[])
GROUP BY n.nspname, tc.relname, ic.relname, am.amname, i.indisunique, i.indisprimary, i.indpred, i.indexrelid
"""


# =============================================================================
# Introspector Implementation
# =============================================================================


@register_introspector("postgresql")
class PostgreSQLIntrospector(Introspector):
    """
    PostgreSQL database introspector.
    
    Uses asyncpg for async database access and queries the PostgreSQL
    system catalogs directly for comprehensive schema information.
    
    Example:
        >>> async with PostgreSQLIntrospector("postgresql://localhost/mydb") as pg:
        ...     result = await pg.introspect()
        ...     print(f"Found {result.table_count} tables")
    """

    def __init__(self, dsn: str) -> None:
        super().__init__(dsn)
        self._conn: Connection | None = None

    @property
    def engine(self) -> str:
        return "postgresql"

    async def _connect(self) -> None:
        """Establish connection to PostgreSQL."""
        try:
            self._conn = await asyncpg.connect(self._dsn)
            self._connected = True
        except Exception as e:
            raise IntrospectionError(
                f"Failed to connect to PostgreSQL: {e}",
                engine=self.engine,
                cause=e,
            ) from e

    async def _get_engine_version(self) -> str | None:
        """Get PostgreSQL version."""
        if self._conn is None:
            return None
        row = await self._conn.fetchrow("SELECT version()")
        if row:
            # Extract version from string like "PostgreSQL 16.1 on ..."
            version_str = row[0]
            parts = version_str.split()
            if len(parts) >= 2:
                return parts[1]
        return None

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            self._connected = False

    def _should_include_table(
        self,
        table_name: str,
        schema_name: str,
        config: IntrospectionConfig,
    ) -> bool:
        """Check if a table should be included based on config."""
        fqn = f"{schema_name}.{table_name}"
        
        # Check explicit includes
        if config.include_tables is not None:
            return (
                table_name in config.include_tables
                or fqn in config.include_tables
            )
        
        # Check excludes
        for pattern in config.exclude_tables:
            if fnmatch.fnmatch(table_name, pattern):
                return False
            if fnmatch.fnmatch(fqn, pattern):
                return False
        
        return True

    async def _introspect_tables(
        self,
        config: IntrospectionConfig,
    ) -> list[Table]:
        """Introspect all tables matching the configuration."""
        if self._conn is None:
            raise IntrospectionError(
                "Not connected to database",
                engine=self.engine,
            )

        # Determine which relation kinds to include
        rel_kinds = ["r"]  # regular tables
        if config.include_views:
            rel_kinds.append("v")
        if config.include_materialized_views:
            rel_kinds.append("m")
        if config.include_partitions:
            rel_kinds.append("p")

        # Fetch tables
        table_rows = await self._conn.fetch(
            _TABLES_QUERY, list(config.schemas), rel_kinds
        )

        # Fetch columns in bulk
        column_rows = await self._conn.fetch(
            _COLUMNS_QUERY, list(config.schemas), rel_kinds
        )

        # Group columns by table
        columns_by_table: dict[str, list[Column]] = {}
        for row in column_rows:
            table_fqn = row["table_fqn"]
            
            # Parse data type
            category, is_array, element_type = _categorize_type(row["type_name"])
            data_type = DataType(
                raw=row["data_type"],
                category=category,
                is_array=is_array,
                element_type=element_type,
            )
            
            column = Column(
                name=row["column_name"],
                data_type=data_type,
                nullable=not row["not_null"],
                default=row["default_value"],
                is_identity=row["is_identity"],
                is_generated=row["is_generated"],
                comment=row["column_comment"] if config.include_comments else None,
                ordinal_position=row["ordinal_position"],
            )
            
            if table_fqn not in columns_by_table:
                columns_by_table[table_fqn] = []
            columns_by_table[table_fqn].append(column)

        # Build table objects
        tables: list[Table] = []
        for row in table_rows:
            table_name = row["table_name"]
            schema_name = row["schema_name"]
            
            if not self._should_include_table(table_name, schema_name, config):
                continue
            
            fqn = f"{schema_name}.{table_name}"
            
            table = Table(
                name=table_name,
                schema=schema_name,
                columns=columns_by_table.get(fqn, []),
                comment=row["table_comment"] if config.include_comments else None,
                row_estimate=row["row_estimate"] if config.include_row_estimates else None,
            )
            tables.append(table)

        return tables

    async def _introspect_constraints(
        self,
        tables: list[Table],
        config: IntrospectionConfig,
    ) -> None:
        """Introspect constraints for the given tables."""
        if self._conn is None:
            return

        # Create lookup for tables by FQN
        table_lookup = {t.fqn: t for t in tables}

        # Fetch primary keys
        pk_rows = await self._conn.fetch(_PRIMARY_KEYS_QUERY, list(config.schemas))
        for row in pk_rows:
            table_fqn = row["table_fqn"]
            if table_fqn in table_lookup:
                table_lookup[table_fqn].primary_key = PrimaryKey(
                    name=row["constraint_name"],
                    columns=tuple(row["columns"]),
                )

        # Fetch foreign keys
        fk_rows = await self._conn.fetch(_FOREIGN_KEYS_QUERY, list(config.schemas))
        
        # Map action codes to names
        action_map = {
            "a": "NO ACTION",
            "r": "RESTRICT",
            "c": "CASCADE",
            "n": "SET NULL",
            "d": "SET DEFAULT",
        }
        
        for row in fk_rows:
            table_fqn = row["source_table"]
            if table_fqn in table_lookup:
                target_fqn = row["target_table"]
                # Parse target schema and table
                if "." in target_fqn:
                    target_schema, target_table = target_fqn.split(".", 1)
                else:
                    target_schema = "public"
                    target_table = target_fqn
                
                fk = ForeignKey(
                    name=row["constraint_name"],
                    columns=tuple(row["source_columns"]),
                    target_schema=target_schema,
                    target_table=target_table,
                    target_columns=tuple(row["target_columns"]),
                    on_update=action_map.get(row["on_update"], "NO ACTION"),
                    on_delete=action_map.get(row["on_delete"], "NO ACTION"),
                )
                table_lookup[table_fqn].foreign_keys.append(fk)

        # Fetch unique constraints
        unique_rows = await self._conn.fetch(
            _UNIQUE_CONSTRAINTS_QUERY, list(config.schemas)
        )
        for row in unique_rows:
            table_fqn = row["table_fqn"]
            if table_fqn in table_lookup:
                constraint = Constraint(
                    name=row["constraint_name"],
                    constraint_type=ConstraintType.UNIQUE,
                    columns=tuple(row["columns"]),
                )
                table_lookup[table_fqn].constraints.append(constraint)

        # Fetch check constraints
        check_rows = await self._conn.fetch(
            _CHECK_CONSTRAINTS_QUERY, list(config.schemas)
        )
        for row in check_rows:
            table_fqn = row["table_fqn"]
            if table_fqn in table_lookup:
                constraint = Constraint(
                    name=row["constraint_name"],
                    constraint_type=ConstraintType.CHECK,
                    expression=row["definition"],
                )
                table_lookup[table_fqn].constraints.append(constraint)

    async def _introspect_indexes(
        self,
        tables: list[Table],
        config: IntrospectionConfig,
    ) -> None:
        """Introspect indexes for the given tables."""
        if self._conn is None:
            return

        # Create lookup for tables by FQN
        table_lookup = {t.fqn: t for t in tables}

        # Fetch indexes
        index_rows = await self._conn.fetch(_INDEXES_QUERY, list(config.schemas))
        
        for row in index_rows:
            table_fqn = row["table_fqn"]
            if table_fqn not in table_lookup:
                continue
            
            table = table_lookup[table_fqn]
            
            columns = tuple(row["columns"]) if row["columns"] else ()
            expressions = tuple(row["expressions"]) if row["expressions"] else ()
            
            index = Index(
                name=row["index_name"],
                table_schema=table.schema,
                table_name=table.name,
                columns=columns,
                method=_map_index_method(row["index_method"]),
                is_unique=row["is_unique"],
                is_primary=row["is_primary"],
                is_partial=row["predicate"] is not None,
                predicate=row["predicate"],
                expression_columns=expressions,
            )
            table.indexes.append(index)
