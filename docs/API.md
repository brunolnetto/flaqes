# flaqes API Documentation

> **Version:** 0.1.0  
> **Last Updated:** 2026-01-15

This document provides detailed API documentation for the flaqes library.

---

## Table of Contents

1. [Core API](#core-api)
   - [analyze_schema](#analyze_schema)
   - [introspect_schema](#introspect_schema)
   - [generate_report](#generate_report)
2. [Data Types](#data-types)
   - [Intent](#intent)
   - [SchemaGraph](#schemagraph)
   - [SchemaReport](#schemareport)
3. [Analysis Components](#analysis-components)
   - [RoleDetector](#roledetector)
   - [PatternDetector](#patterndetector)
   - [TensionAnalyzer](#tensionanalyzer)
4. [DDL Parsing](#ddl-parsing)
5. [CLI Reference](#cli-reference)

---

## Core API

### `analyze_schema`

```python
async def analyze_schema(
    dsn: str,
    intent: Intent | None = None,
    tables: list[str] | None = None,
    schemas: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> SchemaReport
```

Analyze a database schema and generate a comprehensive report.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `dsn` | `str` | Database connection string (e.g., `"postgresql://user:pass@host/db"`) |
| `intent` | `Intent \| None` | Optional workload intent for contextual analysis |
| `tables` | `list[str] \| None` | Optional list of specific tables to analyze |
| `schemas` | `list[str] \| None` | Optional list of schemas (default: `["public"]`) |
| `exclude_patterns` | `list[str] \| None` | Optional glob patterns to exclude (e.g., `["tmp_*", "staging_*"]`) |

**Returns:** `SchemaReport` containing all analysis results

**Example:**

```python
import asyncio
from flaqes import analyze_schema, Intent

async def main():
    intent = Intent(workload="OLTP", data_volume="medium")
    
    report = await analyze_schema(
        dsn="postgresql://localhost/mydb",
        intent=intent,
        schemas=["public", "app"],
        exclude_patterns=["temp_*", "backup_*"],
    )
    
    print(report.to_markdown())

asyncio.run(main())
```

---

### `introspect_schema`

```python
async def introspect_schema(
    dsn: str,
    tables: list[str] | None = None,
    schemas: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> SchemaGraph
```

Introspect a database and return the raw schema graph without analysis.

This is a lower-level API for custom analysis workflows.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `dsn` | `str` | Database connection string |
| `tables` | `list[str] \| None` | Optional list of specific tables |
| `schemas` | `list[str] \| None` | Optional list of schemas |
| `exclude_patterns` | `list[str] \| None` | Optional patterns to exclude |

**Returns:** `SchemaGraph` containing all structural information

**Example:**

```python
from flaqes import introspect_schema

async def main():
    graph = await introspect_schema("postgresql://localhost/mydb")
    
    for table in graph:
        print(f"{table.fqn}: {len(table.columns)} columns")
        if table.primary_key:
            print(f"  PK: {', '.join(table.primary_key.columns)}")
```

---

### `generate_report`

```python
def generate_report(
    graph: SchemaGraph,
    intent: Intent | None = None,
) -> SchemaReport
```

Generate a report from a schema graph.

Useful when you have a schema graph from DDL parsing or want to separate introspection from analysis.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `graph` | `SchemaGraph` | The schema graph to analyze |
| `intent` | `Intent \| None` | Optional workload intent |

**Returns:** `SchemaReport` with complete analysis

**Example:**

```python
from flaqes import generate_report, Intent
from flaqes.introspection import parse_ddl

ddl = """
CREATE TABLE users (id SERIAL PRIMARY KEY, email TEXT NOT NULL);
CREATE TABLE orders (id SERIAL PRIMARY KEY, user_id INT REFERENCES users(id));
"""

graph = parse_ddl(ddl)
report = generate_report(graph, intent=Intent(workload="OLTP"))
print(report.to_markdown())
```

---

## Data Types

### `Intent`

```python
@dataclass
class Intent:
    workload: Literal["OLTP", "OLAP", "mixed"] = "mixed"
    write_frequency: Literal["high", "medium", "low"] = "medium"
    read_patterns: list[ReadPattern] = field(default_factory=list)
    consistency: Literal["strong", "eventual"] = "strong"
    evolution_rate: Literal["high", "medium", "low", "frozen"] = "medium"
    data_volume: Literal["small", "medium", "large", "massive"] = "medium"
```

Represents the intended workload characteristics for analysis.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workload` | `str` | `"mixed"` | Primary workload type: OLTP, OLAP, or mixed |
| `write_frequency` | `str` | `"medium"` | How often data is written |
| `read_patterns` | `list` | `[]` | Types of read operations: point_lookup, range_scan, aggregation, join_heavy |
| `consistency` | `str` | `"strong"` | Consistency requirements |
| `evolution_rate` | `str` | `"medium"` | How often schema changes |
| `data_volume` | `str` | `"medium"` | Expected data size |

**Presets:**

```python
from flaqes.core.intent import (
    OLTP_INTENT,           # Transactional: strong consistency, point lookups
    OLAP_INTENT,           # Analytics: aggregations, range scans
    EVENT_SOURCING_INTENT, # Append-only: low writes, range scans
    STARTUP_MVP_INTENT,    # Flexibility: high evolution, eventual consistency
)
```

---

### `SchemaGraph`

```python
class SchemaGraph:
    tables: dict[str, Table]
    relationships: list[Relationship]
```

Represents a database schema as a graph of tables and relationships.

**Key Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `__iter__()` | `Iterator[Table]` | Iterate over all tables |
| `get_table(fqn: str)` | `Table \| None` | Get table by fully-qualified name |
| `get_table_by_name(name: str)` | `Table \| None` | Get table by simple name |
| `get_relationships_for(table_fqn: str)` | `list[Relationship]` | Get relationships involving a table |

**Example:**

```python
for table in graph:
    print(f"Table: {table.fqn}")
    print(f"  Columns: {[c.name for c in table.columns]}")
    print(f"  FKs: {len(table.foreign_keys)}")
    
# Get specific table
users = graph.get_table_by_name("users")
```

---

### `SchemaReport`

```python
@dataclass
class SchemaReport:
    graph: SchemaGraph
    table_roles: dict[str, RoleDetectionResult]
    patterns: list[PatternMatch]
    tensions: list[DesignTension]
    intent: Intent | None
```

The complete analysis result.

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `table_count` | `int` | Number of tables analyzed |
| `relationship_count` | `int` | Number of relationships found |
| `table_roles` | `dict` | Role detection results by table FQN |
| `patterns` | `list` | All detected design patterns |
| `tensions` | `list` | All detected design tensions |

**Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `to_markdown()` | `str` | Formatted markdown report |
| `to_dict()` | `dict` | JSON-serializable dictionary |

---

## Analysis Components

### `RoleDetector`

Detects semantic roles for tables (fact, dimension, event, junction, etc.).

```python
from flaqes.analysis import RoleDetector

detector = RoleDetector()
result = detector.detect(table, graph)

print(f"Primary role: {result.primary_role.name}")
print(f"Confidence: {result.confidence:.0%}")
print(f"Signals: {[s.name for s in result.signals]}")
```

**Detected Roles:**

| Role | Description |
|------|-------------|
| `FACT` | Measures/metrics with FK references |
| `DIMENSION` | Descriptive attributes, referenced by facts |
| `EVENT` | Append-only event/audit logs |
| `JUNCTION` | Many-to-many relationship tables |
| `CONFIG` | Application configuration |
| `LOOKUP` | Small reference tables (status codes, etc.) |
| `SNAPSHOT` | Point-in-time copies |
| `STAGING` | Temporary/ETL tables |
| `UNKNOWN` | Could not determine role |

---

### `PatternDetector`

Detects design patterns in tables.

```python
from flaqes.analysis import PatternDetector

detector = PatternDetector()
patterns = detector.detect(table, graph)

for pattern in patterns:
    print(f"Pattern: {pattern.pattern_type.name}")
    print(f"Confidence: {pattern.confidence:.0%}")
```

**Detected Patterns:**

| Pattern | Description |
|---------|-------------|
| `SCD_TYPE_1` | Slowly changing dimension (overwrite) |
| `SCD_TYPE_2` | Slowly changing dimension (history) |
| `SOFT_DELETE` | Logical deletion with deleted_at column |
| `AUDIT_TIMESTAMPS` | created_at/updated_at columns |
| `POLYMORPHIC` | Type discriminator with nullable columns |
| `JSONB_FLEXIBLE` | JSONB for schema flexibility |
| `NATURAL_KEY` | Non-surrogate primary key |

---

### `TensionAnalyzer`

Analyzes design tensions based on intent.

```python
from flaqes.analysis import TensionAnalyzer
from flaqes import Intent

analyzer = TensionAnalyzer(intent=Intent(workload="OLTP"))
tensions = analyzer.analyze_table(table, graph)

for tension in tensions:
    print(f"[{tension.severity.name}] {tension.description}")
    print(f"  Risk: {tension.risk}")
    print(f"  Breaking point: {tension.breaking_point}")
    for alt in tension.alternatives:
        print(f"  Alternative: {alt.description} ({alt.effort.value} effort)")
```

**Tension Categories:**

| Category | Description |
|----------|-------------|
| `NORMALIZATION` | Over/under normalization issues |
| `PERFORMANCE` | Missing indexes, wide tables |
| `EVOLUTION` | Schema flexibility concerns |
| `CONSISTENCY` | Data integrity risks |

---

## DDL Parsing

Parse DDL without database connection.

### `parse_ddl`

```python
from flaqes.introspection import parse_ddl

ddl = """
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL
);
"""

graph = parse_ddl(ddl, default_schema="public")
```

### `parse_ddl_file`

```python
from flaqes.introspection import parse_ddl_file

graph = parse_ddl_file("schema.sql")
graph = parse_ddl_file("schema.sql", default_schema="myapp")
```

### `DDLParser` (Advanced)

```python
from flaqes.introspection import DDLParser

parser = DDLParser(default_schema="public")
result = parser.parse(ddl_string)

if result.errors:
    for error in result.errors:
        print(f"Line {error.line}: {error.message}")
else:
    for table in result.tables:
        print(f"Parsed: {table.name}")
    
    # Convert to SchemaGraph
    graph = parser.to_schema_graph(result)
```

---

## CLI Reference

### `flaqes analyze`

Analyze a live PostgreSQL database.

```bash
flaqes analyze <dsn> [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--workload` | Workload type: OLTP, OLAP, mixed |
| `--volume` | Data volume: small, medium, large, massive |
| `--format` | Output format: markdown (default), json |
| `--tables` | Specific tables to analyze (comma-separated) |
| `--schemas` | Schemas to include (comma-separated) |

**Examples:**

```bash
flaqes analyze postgresql://localhost/mydb
flaqes analyze postgresql://localhost/mydb --workload OLTP --format json
flaqes analyze postgresql://user:pass@host/db --tables users,orders
```

---

### `flaqes analyze-ddl`

Analyze DDL files without database connection.

```bash
flaqes analyze-ddl <files...> [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--schema` | Default schema name (default: public) |
| `--workload` | Workload type |
| `--volume` | Data volume |
| `--format` | Output format: markdown (default), json |

**Examples:**

```bash
flaqes analyze-ddl schema.sql
flaqes analyze-ddl schema.sql migrations/*.sql --schema myapp
flaqes analyze-ddl schema.sql --format json
```

---

### `flaqes introspect`

Introspect database structure only (no analysis).

```bash
flaqes introspect --dsn <dsn> [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--dsn` | Database connection string (required) |
| `--format` | Output format: text (default), json |

**Examples:**

```bash
flaqes introspect --dsn postgresql://localhost/mydb
flaqes introspect --dsn postgresql://localhost/mydb --format json
```

---

## Error Handling

### `IntrospectionError`

Raised when database introspection fails.

```python
from flaqes.introspection.base import IntrospectionError

try:
    report = await analyze_schema(dsn)
except IntrospectionError as e:
    print(f"Failed to introspect {e.engine}: {e}")
    if e.cause:
        print(f"Caused by: {e.cause}")
```

### `ParseError`

Returned when DDL parsing encounters issues.

```python
from flaqes.introspection import DDLParser

parser = DDLParser()
result = parser.parse(ddl)

if result.errors:
    for error in result.errors:
        print(f"Parse error at line {error.line}: {error.message}")
        print(f"Context: {error.context}")
```

---

## See Also

- [Implementation Plan](IMPLEMENTATION_PLAN.md) - Architecture details
- [GitHub Repository](https://github.com/brunolnetto/flaqes)
- [Issue Tracker](https://github.com/brunolnetto/flaqes/issues)
