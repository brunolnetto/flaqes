# flaqes 🔍

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Coverage: 100%](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://github.com/brunolnetto/flaqes)

**A schema critic for PostgreSQL databases**

flaqes analyzes database structures and surfaces design tensions, trade-offs, and alternative approaches based on your stated intent. Think of it as a thoughtful colleague who reviews your schema and explains *why* things are the way they are, not just *what* they are.

## Features

- 🎯 **Intent-Aware Analysis** - Provides contextual advice based on your workload (OLTP, OLAP, or mixed)
- 🔍 **Role Detection** - Identifies semantic roles (fact tables, dimensions, events, junctions, etc.) with confidence scores
- 🎨 **Pattern Recognition** - Detects design patterns like SCD Type 2, soft deletes, polymorphic associations, and more
- ⚖️ **Design Tensions** - Surfaces trade-offs in your current design with alternatives and effort estimates
- 📊 **Comprehensive Reports** - Generates structured reports in Markdown or JSON format
- 📈 **Mermaid ERD Diagrams** - Generate beautiful entity-relationship diagrams for documentation
- 🖥️ **CLI Interface** - Analyze databases or DDL files from the command line
- 📄 **DDL Parsing** - Analyze schema from DDL files without database connection
- 🔬 **No Mutations** - Analysis only, never modifies your database

## Installation

```bash
# Basic installation (includes PostgreSQL support)
pip install flaqes

# With development dependencies
pip install flaqes[dev]
```

Or using `uv`:

```bash
uv pip install flaqes
```

## Quick Start

### Python API

```python
import asyncio
from flaqes import analyze_schema, Intent

async def main():
    # Define your workload intent
    intent = Intent(
        workload="OLAP",
        write_frequency="low",
        read_patterns=["aggregation", "range_scan"],
        data_volume="large",
        evolution_rate="high",
    )
    
    # Analyze your database
    report = await analyze_schema(
        dsn="postgresql://user:pass@localhost/mydb",
        intent=intent,
    )
    
    # View the markdown report
    print(report.to_markdown())
    
    # Or export as JSON
    import json
    print(json.dumps(report.to_dict(), indent=2))

asyncio.run(main())
```

### Command Line Interface

```bash
# Analyze a live PostgreSQL database
flaqes analyze postgresql://user:pass@localhost/mydb

# Analyze with workload intent
flaqes analyze postgresql://localhost/mydb --workload OLTP --volume small

# Output as JSON
flaqes analyze postgresql://localhost/mydb --format json

# Analyze DDL files (no database connection required)
flaqes analyze-ddl schema.sql

# Multiple DDL files
flaqes analyze-ddl schema.sql migrations/*.sql

# Introspect schema structure only
flaqes introspect --dsn postgresql://localhost/mydb
flaqes introspect --dsn postgresql://localhost/mydb --format json

# Generate Mermaid ERD diagram
flaqes diagram --ddl schema.sql
flaqes diagram --ddl schema.sql --wrap  # Wrap in markdown code block
flaqes diagram --ddl schema.sql --no-columns  # Tables only, no column details
flaqes diagram --dsn postgresql://localhost/mydb  # From live database
```

## What Makes flaqes Different?

Unlike traditional schema validators or linters, flaqes:

1. **Understands Intent** - Recommendations depend on your workload. A denormalized table might be problematic for OLTP but perfect for OLAP.

2. **Embraces Uncertainty** - Every inference includes a confidence score and the signals that led to it. No black-box "best practices."

3. **Explains Trade-offs** - Instead of saying "this is wrong," flaqes says "here's what you gain, here's what you risk, and here's when it might break."

4. **Never Mutates** - flaqes is read-only. It analyzes and advises, never changes your database.

## Example Output

```markdown
# Schema Analysis Report: public

**Tables analyzed:** 12
**Workload:** OLAP
**Data volume:** large

## Summary

### Table Roles
- **FACT**: 3
- **DIMENSION**: 6
- **JUNCTION**: 2
- **EVENT**: 1

### Design Patterns
- **AUDIT_TIMESTAMPS**: 8
- **SOFT_DELETE**: 4
- **SCD_TYPE_2**: 2

### Design Tensions
- 🔴 **Critical**: 2
- 🟡 **Warning**: 5
- 🔵 **Info**: 3

---

## Design Tensions

### 🔴 Critical Issues

#### public.orders: Missing index on frequently joined column
**Risk:** Full table scans on large table during joins will severely impact query performance.
**Breaking point:** When table exceeds 100K rows or join queries exceed 1s response time.
**Alternatives:** 2
- Add B-tree index on customer_id (low effort)
- Partition table by order_date and add local indexes (medium effort)
```

## API Reference

### Core Functions

#### `analyze_schema`

Analyze a database schema and generate a comprehensive report.

```python
async def analyze_schema(
    dsn: str,
    intent: Intent | None = None,
    tables: list[str] | None = None,
    schemas: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> SchemaReport:
```

**Parameters:**
- `dsn`: Database connection string (e.g., `"postgresql://user:pass@host/db"`)
- `intent`: Optional workload intent for contextual analysis
- `tables`: Optional list of specific tables to analyze
- `schemas`: Optional list of schemas (default: `["public"]`)
- `exclude_patterns`: Optional patterns to exclude (e.g., `["tmp_*"]`)

**Returns:** `SchemaReport` with analysis results

#### `introspect_schema`

Introspect a database and return the raw schema graph.

```python
async def introspect_schema(
    dsn: str,
    tables: list[str] | None = None,
    schemas: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> SchemaGraph:
```

#### `generate_report`

Generate a report from a schema graph.

```python
def generate_report(
    graph: SchemaGraph,
    intent: Intent | None = None,
) -> SchemaReport:
```

### DDL Parsing

Analyze schemas directly from DDL files:

```python
from flaqes.introspection import parse_ddl, parse_ddl_file
from flaqes import generate_report, Intent

# Parse DDL string
ddl = """
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);
"""
graph = parse_ddl(ddl)

# Parse DDL file
graph = parse_ddl_file("schema.sql")

# Analyze
report = generate_report(graph, intent=Intent(workload="OLTP"))
print(report.to_markdown())
```

### Intent Specification

The `Intent` dataclass captures your workload characteristics:

```python
from flaqes import Intent

intent = Intent(
    workload="OLTP",           # "OLTP" | "OLAP" | "mixed"
    write_frequency="high",     # "high" | "medium" | "low"
    read_patterns=["point_lookup", "join_heavy"],  # List of patterns
    consistency="strong",       # "strong" | "eventual"
    evolution_rate="high",      # "high" | "medium" | "low" | "frozen"
    data_volume="medium",       # "small" | "medium" | "large" | "massive"
)
```

**Common presets:**

```python
from flaqes.core.intent import (
    OLTP_INTENT,           # High-frequency transactional workload
    OLAP_INTENT,           # Analytics/reporting workload
    EVENT_SOURCING_INTENT, # Append-only event streams
    STARTUP_MVP_INTENT,    # Rapid iteration, schema flexibility
)
```

### Lower-Level API

For custom analysis workflows:

```python
from flaqes import introspect_schema
from flaqes.analysis import RoleDetector, PatternDetector, TensionAnalyzer

# Just introspect the schema
graph = await introspect_schema("postgresql://localhost/mydb")

# Run individual analyzers
role_detector = RoleDetector()
pattern_detector = PatternDetector()
tension_analyzer = TensionAnalyzer(intent=intent)

for table in graph:
    # Detect table role
    role_result = role_detector.detect(table, graph)
    print(f"{table.name}: {role_result.primary_role.name} ({role_result.confidence:.0%})")
    
    # Detect patterns
    patterns = pattern_detector.detect(table, graph)
    for pattern in patterns:
        print(f"  Pattern: {pattern.pattern_type.name}")
    
    # Analyze tensions
    tensions = tension_analyzer.analyze_table(table, graph)
    for tension in tensions:
        print(f"  Tension: {tension.description}")
```

### SchemaReport API

```python
report = await analyze_schema(dsn, intent=intent)

# Properties
report.table_count           # Number of tables analyzed
report.table_roles           # Dict[str, RoleResult]
report.patterns              # List of detected patterns
report.tensions              # List of design tensions
report.intent                # The intent used for analysis

# Export methods
report.to_markdown()         # Formatted markdown string
report.to_dict()             # JSON-serializable dictionary
```

## Architecture

flaqes operates in three layers:

```
┌─────────────────────────────────────────────────────────────┐
│                    Intent-Aware Analysis                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Tension   │  │  Severity   │  │    Alternatives     │  │
│  │  Detection  │  │  Scoring    │  │    & Trade-offs     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                  Semantic Heuristics                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │    Role     │  │   Pattern   │  │    Confidence       │  │
│  │  Detection  │  │  Matching   │  │    Scoring          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                   Structural Facts                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Tables    │  │  Indexes &  │  │   Relationships     │  │
│  │ & Columns   │  │ Constraints │  │   & Cardinality     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│         PostgreSQL Catalog / DDL Parser                      │
└─────────────────────────────────────────────────────────────┘
```

1. **Structural Facts Layer** (Objective)
   - Introspects database catalogs or parses DDL
   - Extracts tables, columns, keys, constraints, indexes
   - Builds a complete `SchemaGraph`

2. **Semantic Heuristics Layer** (Probabilistic)
   - Detects table roles via structural signals
   - Identifies design patterns via naming and structure
   - All with confidence scores

3. **Intent-Aware Analysis Layer** (Advisory)
   - Analyzes design tensions based on stated intent
   - Proposes alternatives with trade-off explanations
   - Severity depends on workload characteristics

## Development Status

**Version:** 0.1.0

### Completed ✅
- ✅ PostgreSQL introspection (live database)
- ✅ DDL parsing (offline analysis)
- ✅ Role detection (fact, dimension, event, junction, config, lookup, etc.)
- ✅ Pattern matching (SCD, soft delete, polymorphic, audit, JSONB, etc.)
- ✅ Tension analysis (normalization, performance, evolution)
- ✅ Report generation (Markdown, JSON)
- ✅ CLI interface (`flaqes analyze`, `flaqes analyze-ddl`, `flaqes introspect`)
- ✅ Comprehensive test suite (100% coverage)

### Roadmap 🚧
- [ ] MySQL support
- [ ] SQLite support
- [ ] Historical schema tracking
- [ ] LLM integration for natural language explanations
- [ ] VS Code extension

## Requirements

- Python 3.13+
- PostgreSQL 12+ (for database introspection)
- asyncpg (included by default)
- Docker (for running integration tests)

## Contributing

Contributions welcome! This is an early-stage project.

```bash
# Clone and install
git clone https://github.com/brunolnetto/flaqes.git
cd flaqes
uv pip install -e .[dev]

# Run tests
uv run pytest

# Run with integration tests (requires Docker)
uv run pytest --run-integration

# Check coverage
uv run pytest --cov=flaqes --cov-report=term-missing
```

See [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for architecture details.

## License

MIT License - see LICENSE file for details

## Acknowledgments

Inspired by the need for thoughtful schema review tools that understand context and trade-offs rather than enforcing rigid "best practices."

---

**flaqes** - *Because your schema deserves a thoughtful review, not just a lint check.*
