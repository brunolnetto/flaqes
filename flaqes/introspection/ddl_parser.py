"""
DDL Parser for offline schema analysis.

This module parses CREATE TABLE statements to build a SchemaGraph
without requiring a live database connection. Useful for:
- Analyzing schema files from version control
- CI/CD pipeline integration
- Reviewing proposed schema changes
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from flaqes.core.schema_graph import (
    Column,
    Constraint,
    DataType,
    ForeignKey,
    Index,
    PrimaryKey,
    SchemaGraph,
    Table,
)
from flaqes.core.types import ConstraintType, DataTypeCategory, IndexMethod

if TYPE_CHECKING:
    pass


@dataclass
class ParseError:
    """Represents a parsing error."""
    
    line: int
    message: str
    context: str


@dataclass
class ParseResult:
    """Result of parsing DDL statements."""
    
    tables: list[Table]
    errors: list[ParseError]
    
    @property
    def success(self) -> bool:
        """Check if parsing was successful (no errors)."""
        return len(self.errors) == 0


# Data type mapping to categories
TYPE_CATEGORY_MAP: dict[str, DataTypeCategory] = {
    # Integer types
    "integer": DataTypeCategory.INTEGER,
    "int": DataTypeCategory.INTEGER,
    "int4": DataTypeCategory.INTEGER,
    "int8": DataTypeCategory.INTEGER,
    "bigint": DataTypeCategory.INTEGER,
    "smallint": DataTypeCategory.INTEGER,
    "int2": DataTypeCategory.INTEGER,
    "serial": DataTypeCategory.INTEGER,
    "bigserial": DataTypeCategory.INTEGER,
    "smallserial": DataTypeCategory.INTEGER,
    
    # Float types
    "real": DataTypeCategory.FLOAT,
    "float4": DataTypeCategory.FLOAT,
    "double precision": DataTypeCategory.FLOAT,
    "float8": DataTypeCategory.FLOAT,
    "float": DataTypeCategory.FLOAT,
    
    # Decimal types
    "numeric": DataTypeCategory.DECIMAL,
    "decimal": DataTypeCategory.DECIMAL,
    "money": DataTypeCategory.DECIMAL,
    
    # Text
    "text": DataTypeCategory.TEXT,
    "varchar": DataTypeCategory.TEXT,
    "character varying": DataTypeCategory.TEXT,
    "char": DataTypeCategory.TEXT,
    "character": DataTypeCategory.TEXT,
    "bpchar": DataTypeCategory.TEXT,
    "name": DataTypeCategory.TEXT,
    "citext": DataTypeCategory.TEXT,
    
    # Boolean
    "boolean": DataTypeCategory.BOOLEAN,
    "bool": DataTypeCategory.BOOLEAN,
    
    # Timestamp types
    "timestamp": DataTypeCategory.TIMESTAMP,
    "timestamptz": DataTypeCategory.TIMESTAMP,
    "timestamp with time zone": DataTypeCategory.TIMESTAMP,
    "timestamp without time zone": DataTypeCategory.TIMESTAMP,
    
    # Date type
    "date": DataTypeCategory.DATE,
    
    # Time types
    "time": DataTypeCategory.TIME,
    "timetz": DataTypeCategory.TIME,
    "time with time zone": DataTypeCategory.TIME,
    
    # Interval
    "interval": DataTypeCategory.INTERVAL,
    
    # UUID
    "uuid": DataTypeCategory.UUID,
    
    # JSON
    "json": DataTypeCategory.JSON,
    "jsonb": DataTypeCategory.JSON,
    
    # Binary
    "bytea": DataTypeCategory.BINARY,
    
    # Array (will be overridden)
    "array": DataTypeCategory.ARRAY,
}


def _categorize_type(type_str: str) -> tuple[DataTypeCategory, bool, str | None]:
    """
    Categorize a PostgreSQL type string.
    
    Returns:
        Tuple of (category, is_array, element_type)
    """
    type_lower = type_str.lower().strip()
    
    # Check for array types
    is_array = False
    element_type = None
    
    if type_lower.endswith("[]"):
        is_array = True
        element_type = type_lower[:-2]
        type_lower = element_type
    elif type_lower.startswith("array"):
        is_array = True
        # Try to extract element type from ARRAY[type] syntax
        match = re.match(r"array\[(\w+)\]", type_lower)
        if match:
            element_type = match.group(1)
            type_lower = element_type
    
    # Remove size specifications like varchar(255)
    base_type = re.sub(r"\([^)]*\)", "", type_lower).strip()
    
    if is_array:
        return DataTypeCategory.ARRAY, True, element_type
    
    category = TYPE_CATEGORY_MAP.get(base_type, DataTypeCategory.OTHER)
    return category, is_array, element_type


def _parse_data_type(type_str: str) -> DataType:
    """Parse a data type string into a DataType object."""
    category, is_array, element_type = _categorize_type(type_str)
    return DataType(
        raw=type_str.strip(),
        category=category,
        is_array=is_array,
        element_type=element_type,
    )


class DDLParser:
    """
    Parser for PostgreSQL DDL (CREATE TABLE) statements.
    
    Example:
        >>> parser = DDLParser()
        >>> result = parser.parse('''
        ...     CREATE TABLE users (
        ...         id SERIAL PRIMARY KEY,
        ...         email VARCHAR(255) NOT NULL UNIQUE,
        ...         created_at TIMESTAMP DEFAULT NOW()
        ...     );
        ... ''')
        >>> print(result.tables[0].name)
        users
    """
    
    def __init__(self, default_schema: str = "public") -> None:
        """
        Initialize the parser.
        
        Args:
            default_schema: Schema to use when not specified in DDL.
        """
        self.default_schema = default_schema
    
    def parse(self, ddl: str) -> ParseResult:
        """
        Parse DDL statements and extract table definitions.
        
        Args:
            ddl: String containing one or more CREATE TABLE statements.
        
        Returns:
            ParseResult with extracted tables and any parse errors.
        """
        tables: list[Table] = []
        errors: list[ParseError] = []
        
        # Find all CREATE TABLE statements
        pattern = re.compile(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
            r"(?:\"?(\w+)\"?\.)?\"?(\w+)\"?\s*\("
            r"(.*?)"
            r"\)\s*;",
            re.IGNORECASE | re.DOTALL
        )
        
        for match in pattern.finditer(ddl):
            schema = match.group(1) or self.default_schema
            table_name = match.group(2)
            columns_section = match.group(3)
            
            try:
                table = self._parse_table(schema, table_name, columns_section)
                tables.append(table)
            except Exception as e:  # pragma: no cover
                line_num = ddl[:match.start()].count("\n") + 1
                errors.append(ParseError(
                    line=line_num,
                    message=str(e),
                    context=match.group(0)[:100],
                ))
        
        return ParseResult(tables=tables, errors=errors)
    
    def parse_file(self, path: str) -> ParseResult:
        """
        Parse a DDL file.
        
        Args:
            path: Path to the DDL file.
        
        Returns:
            ParseResult with extracted tables and any parse errors.
        """
        with open(path, encoding="utf-8") as f:
            return self.parse(f.read())
    
    def _parse_table(
        self,
        schema: str,
        name: str,
        columns_section: str,
    ) -> Table:
        """Parse a single table definition."""
        columns: list[Column] = []
        constraints: list[Constraint] = []
        foreign_keys: list[ForeignKey] = []
        primary_key: PrimaryKey | None = None
        indexes: list[Index] = []
        
        # Split by commas, but respect parentheses
        parts = self._split_definitions(columns_section)
        
        ordinal = 0
        for part in parts:
            part = part.strip()
            if not part:  # pragma: no cover
                continue
            
            # Check if it's a table-level constraint
            upper_part = part.upper()
            
            if upper_part.startswith("PRIMARY KEY"):
                pk_cols = self._extract_columns_from_constraint(part)
                primary_key = PrimaryKey(name=None, columns=tuple(pk_cols))
            
            elif upper_part.startswith("FOREIGN KEY"):
                fk = self._parse_foreign_key(part)
                if fk:
                    foreign_keys.append(fk)
            
            elif upper_part.startswith("UNIQUE"):
                cols = self._extract_columns_from_constraint(part)
                constraints.append(Constraint(
                    name=None,
                    constraint_type=ConstraintType.UNIQUE,
                    columns=tuple(cols),
                ))
            
            elif upper_part.startswith("CHECK"):
                # Extract check expression
                match = re.search(r"CHECK\s*\((.*)\)", part, re.IGNORECASE)
                expr = match.group(1) if match else part
                constraints.append(Constraint(
                    name=None,
                    constraint_type=ConstraintType.CHECK,
                    expression=expr,
                ))
            
            elif upper_part.startswith("CONSTRAINT"):
                # Named constraint - parse the actual constraint type
                constraint = self._parse_named_constraint(part)
                if constraint:
                    if isinstance(constraint, PrimaryKey):
                        primary_key = constraint
                    elif isinstance(constraint, ForeignKey):
                        foreign_keys.append(constraint)
                    else:
                        constraints.append(constraint)
            
            else:
                # Regular column definition
                col = self._parse_column(part, ordinal)
                if col:
                    columns.append(col)
                    ordinal += 1
                    
                    # Check for inline PRIMARY KEY
                    if "PRIMARY KEY" in part.upper():
                        if primary_key is None:
                            primary_key = PrimaryKey(name=None, columns=(col.name,))
                        else:  # pragma: no cover
                            # Composite PK defined inline - rare but handle it
                            primary_key = PrimaryKey(
                                name=primary_key.name,
                                columns=primary_key.columns + (col.name,),
                            )
                    
                    # Check for inline UNIQUE
                    if " UNIQUE" in part.upper() and "NOT" not in part.upper().split("UNIQUE")[0][-4:]:
                        constraints.append(Constraint(
                            name=None,
                            constraint_type=ConstraintType.UNIQUE,
                            columns=(col.name,),
                        ))
                    
                    # Check for inline REFERENCES (FK)
                    if "REFERENCES" in part.upper():
                        fk = self._parse_inline_foreign_key(col.name, part)
                        if fk:
                            foreign_keys.append(fk)
        
        return Table(
            name=name,
            schema=schema,
            columns=columns,
            primary_key=primary_key,
            foreign_keys=foreign_keys,
            constraints=constraints,
            indexes=indexes,
        )
    
    def _split_definitions(self, section: str) -> list[str]:
        """Split column/constraint definitions respecting parentheses."""
        parts = []
        current = ""
        depth = 0
        
        for char in section:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                parts.append(current.strip())
                current = ""
                continue
            current += char
        
        if current.strip():
            parts.append(current.strip())
        
        return parts
    
    def _parse_column(self, definition: str, ordinal: int) -> Column | None:
        """Parse a column definition."""
        # Basic pattern: column_name type [constraints...]
        # Handle quoted identifiers
        pattern = re.compile(
            r'^"?(\w+)"?\s+(.+)$',
            re.IGNORECASE | re.DOTALL
        )
        
        match = pattern.match(definition.strip())
        if not match:  # pragma: no cover
            return None
        
        name = match.group(1)
        rest = match.group(2).strip()
        
        # Extract the type (first word(s) before constraints)
        # Types can be multi-word like "character varying" or "timestamp with time zone"
        type_and_constraints = rest
        
        # Find where constraints start
        constraint_keywords = [
            "NOT NULL", "NULL", "DEFAULT", "PRIMARY KEY",
            "UNIQUE", "REFERENCES", "CHECK", "CONSTRAINT",
        ]
        
        type_end = len(rest)
        for keyword in constraint_keywords:
            idx = rest.upper().find(keyword)
            if idx != -1 and idx < type_end:
                type_end = idx
        
        type_str = rest[:type_end].strip()
        constraint_str = rest[type_end:].upper()
        
        # Parse nullability
        nullable = "NOT NULL" not in constraint_str
        
        # Parse default
        default = None
        default_match = re.search(r"DEFAULT\s+(.+?)(?:\s+(?:NOT\s+)?NULL|\s+PRIMARY|\s+UNIQUE|\s+REFERENCES|\s+CHECK|$)", rest, re.IGNORECASE)
        if default_match:
            default = default_match.group(1).strip()
        
        # Check for identity/serial
        is_identity = "SERIAL" in type_str.upper() or "GENERATED" in constraint_str
        
        return Column(
            name=name,
            data_type=_parse_data_type(type_str),
            nullable=nullable,
            default=default,
            is_identity=is_identity,
            ordinal_position=ordinal,
        )
    
    def _extract_columns_from_constraint(self, definition: str) -> list[str]:
        """Extract column names from a constraint definition."""
        match = re.search(r"\(([^)]+)\)", definition)
        if not match:  # pragma: no cover
            return []
        
        cols_str = match.group(1)
        return [c.strip().strip('"') for c in cols_str.split(",")]
    
    def _parse_foreign_key(self, definition: str) -> ForeignKey | None:
        """Parse a FOREIGN KEY constraint definition."""
        pattern = re.compile(
            r"FOREIGN\s+KEY\s*\(([^)]+)\)\s*"
            r"REFERENCES\s+(?:\"?(\w+)\"?\.)?\"?(\w+)\"?\s*\(([^)]+)\)"
            r"(?:\s+ON\s+DELETE\s+(\w+(?:\s+\w+)?))?"
            r"(?:\s+ON\s+UPDATE\s+(\w+(?:\s+\w+)?))?",
            re.IGNORECASE
        )
        
        match = pattern.search(definition)
        if not match:  # pragma: no cover
            return None
        
        source_cols = [c.strip().strip('"') for c in match.group(1).split(",")]
        target_schema = match.group(2) or self.default_schema
        target_table = match.group(3)
        target_cols = [c.strip().strip('"') for c in match.group(4).split(",")]
        on_delete = (match.group(5) or "NO ACTION").upper()
        on_update = (match.group(6) or "NO ACTION").upper()
        
        return ForeignKey(
            name=None,
            columns=tuple(source_cols),
            target_schema=target_schema,
            target_table=target_table,
            target_columns=tuple(target_cols),
            on_delete=on_delete,
            on_update=on_update,
        )
    
    def _parse_inline_foreign_key(
        self,
        column: str,
        definition: str,
    ) -> ForeignKey | None:
        """Parse an inline REFERENCES constraint."""
        pattern = re.compile(
            r"REFERENCES\s+(?:\"?(\w+)\"?\.)?\"?(\w+)\"?\s*(?:\(([^)]+)\))?"
            r"(?:\s+ON\s+DELETE\s+(\w+(?:\s+\w+)?))?"
            r"(?:\s+ON\s+UPDATE\s+(\w+(?:\s+\w+)?))?",
            re.IGNORECASE
        )
        
        match = pattern.search(definition)
        if not match:  # pragma: no cover
            return None
        
        target_schema = match.group(1) or self.default_schema
        target_table = match.group(2)
        target_col = match.group(3).strip().strip('"') if match.group(3) else column
        on_delete = (match.group(4) or "NO ACTION").upper()
        on_update = (match.group(5) or "NO ACTION").upper()
        
        return ForeignKey(
            name=None,
            columns=(column,),
            target_schema=target_schema,
            target_table=target_table,
            target_columns=(target_col,),
            on_delete=on_delete,
            on_update=on_update,
        )
    
    def _parse_named_constraint(
        self,
        definition: str,
    ) -> PrimaryKey | ForeignKey | Constraint | None:
        """Parse a named constraint (CONSTRAINT name ...)."""
        # Extract constraint name
        name_match = re.match(r"CONSTRAINT\s+\"?(\w+)\"?\s+(.+)", definition, re.IGNORECASE | re.DOTALL)
        if not name_match:  # pragma: no cover
            return None
        
        constraint_name = name_match.group(1)
        rest = name_match.group(2).strip()
        upper_rest = rest.upper()
        
        if upper_rest.startswith("PRIMARY KEY"):
            cols = self._extract_columns_from_constraint(rest)
            return PrimaryKey(name=constraint_name, columns=tuple(cols))
        
        elif upper_rest.startswith("FOREIGN KEY"):
            fk = self._parse_foreign_key(rest)
            if fk:
                return ForeignKey(
                    name=constraint_name,
                    columns=fk.columns,
                    target_schema=fk.target_schema,
                    target_table=fk.target_table,
                    target_columns=fk.target_columns,
                    on_delete=fk.on_delete,
                    on_update=fk.on_update,
                )
        
        elif upper_rest.startswith("UNIQUE"):
            cols = self._extract_columns_from_constraint(rest)
            return Constraint(
                name=constraint_name,
                constraint_type=ConstraintType.UNIQUE,
                columns=tuple(cols),
            )
        
        elif upper_rest.startswith("CHECK"):
            match = re.search(r"CHECK\s*\((.*)\)", rest, re.IGNORECASE | re.DOTALL)
            expr = match.group(1) if match else rest
            return Constraint(
                name=constraint_name,
                constraint_type=ConstraintType.CHECK,
                expression=expr,
            )
        
        return None  # pragma: no cover
    
    def to_schema_graph(self, result: ParseResult) -> SchemaGraph:
        """
        Convert a ParseResult to a SchemaGraph.
        
        Args:
            result: ParseResult from parsing DDL.
        
        Returns:
            SchemaGraph that can be analyzed.
        """
        return SchemaGraph.from_tables(result.tables)


def parse_ddl(ddl: str, default_schema: str = "public") -> SchemaGraph:
    """
    Convenience function to parse DDL and return a SchemaGraph.
    
    Args:
        ddl: String containing CREATE TABLE statements.
        default_schema: Default schema name when not specified.
    
    Returns:
        SchemaGraph for analysis.
    
    Raises:
        ValueError: If parsing fails with errors.
    
    Example:
        >>> graph = parse_ddl('''
        ...     CREATE TABLE users (
        ...         id SERIAL PRIMARY KEY,
        ...         email VARCHAR(255) NOT NULL
        ...     );
        ... ''')
        >>> for table in graph:
        ...     print(table.name)
        users
    """
    parser = DDLParser(default_schema=default_schema)
    result = parser.parse(ddl)
    
    if result.errors:  # pragma: no cover
        error_msgs = [f"Line {e.line}: {e.message}" for e in result.errors]
        raise ValueError(f"DDL parsing failed:\n" + "\n".join(error_msgs))
    
    return parser.to_schema_graph(result)


def parse_ddl_file(path: str, default_schema: str = "public") -> SchemaGraph:
    """
    Convenience function to parse a DDL file.
    
    Args:
        path: Path to DDL file.
        default_schema: Default schema name when not specified.
    
    Returns:
        SchemaGraph for analysis.
    """
    parser = DDLParser(default_schema=default_schema)
    result = parser.parse_file(path)
    
    if result.errors:  # pragma: no cover
        error_msgs = [f"Line {e.line}: {e.message}" for e in result.errors]
        raise ValueError(f"DDL parsing failed:\n" + "\n".join(error_msgs))
    
    return parser.to_schema_graph(result)
