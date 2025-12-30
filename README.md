# flaqes 🔍

**A schema critic for PostgreSQL databases**

flaqes analyzes database structures and surfaces design tensions, trade-offs, and alternative approaches based on your stated intent.

Think of it as a thoughtful colleague who reviews your schema and tells you:
- **What** you have - tables, columns, relationships, patterns
- **How** it's structured - roles, design patterns, architectural choices  
- **Why** it matters - trade-offs, risks, breaking points, and alternatives

Unlike tools that just catalog structure or enforce rigid rules, flaqes understands *context* and explains *implications*.

## Features

- 🎯 **Intent-Aware Analysis** - Provides contextual advice based on your workload (OLTP, OLAP, or mixed)
- 🔍 **Role Detection** - Identifies semantic roles (fact tables, dimensions, events, junctions, etc.) with confidence scores
- 🎨 **Pattern Recognition** - Detects design patterns like SCD Type 2, soft deletes, polymorphic associations, and more
- ⚖️ **Design Tensions** - Surfaces trade-offs in your current design with alternatives and effort estimates
- 📊 **Comprehensive Reports** - Generates structured reports in Markdown or JSON format
- 📐 **Mermaid ERD Diagrams** - Export visual Entity Relationship Diagrams for documentation
- 🔬 **No Mutations** - Analysis only, never modifies your database

## Installation

```bash
# Basic installation
pip install flaqes

# With PostgreSQL support (required for v0.1)
pip install flaqes[postgresql]

# Development installation
pip install flaqes[dev]
```

Or using `uv`:

```bash
uv pip install flaqes[postgresql]
```

## Quick Start

flaqes supports **three levels of analysis** - use what you need:

### Level 1: WHAT - Just Structure (No Analysis)

Get raw schema facts without any interpretation:

```bash
# CLI: Introspect only (coming soon)
flaqes introspect postgresql://localhost/mydb --format json > schema.json
```

```python
# Python API: Schema structure only
from flaqes import introspect_schema

graph = await introspect_schema("postgresql://localhost/mydb")

# Access raw structure
for table in graph:
    print(f"Table: {table.name}")
    print(f"Columns: {[c.name for c in table.columns]}")
    print(f"Foreign Keys: {[fk.name for fk in table.foreign_keys]}")
```

### Level 2: HOW - Structure + Patterns

Get structure detection without recommendations:

```python
from flaqes import introspect_schema
from flaqes.analysis import RoleDetector, PatternDetector

graph = await introspect_schema("postgresql://localhost/mydb")

# Detect what tables ARE (roles)
role_detector = RoleDetector()
for table in graph:
    role = role_detector.detect(table, graph)
    print(f"{table.name}: {role.primary_role.name} ({role.confidence:.0%})")

# Detect HOW they're designed (patterns)
pattern_detector = PatternDetector()
patterns = pattern_detector.detect_schema_patterns(graph)
for table_name, table_patterns in patterns.items():
    for pattern in table_patterns:
        print(f"{table_name}: {pattern.pattern_type.name}")
```

### Level 3: WHY - Full Analysis with Recommendations

Complete analysis with context-aware advice:

#### Command-Line Interface

```bash
# Full analysis with default intent
flaqes analyze postgresql://user:pass@localhost/mydb

# With specific workload intent
flaqes analyze --intent olap postgresql://localhost/mydb

# Analyze specific tables
flaqes analyze --tables users,orders --output report.md postgresql://localhost/mydb

# JSON output for automation
flaqes analyze --format json --output report.json postgresql://localhost/mydb
```

### Bonus: Visualize with Mermaid ERD

Generate Entity Relationship Diagrams for documentation:

```bash
# Generate Mermaid ERD diagram
flaqes diagram postgresql://localhost/mydb --output schema.mmd

# Include specific tables only
flaqes diagram --tables users,orders,products postgresql://localhost/mydb

# Copy output and paste at https://mermaid.live/ to view
flaqes diagram postgresql://localhost/mydb | pbcopy
```

See the [CLI Guide](docs/CLI_GUIDE.md) for comprehensive usage examples.

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

## What Makes flaqes Different?

Most schema tools tell you **what** you have. Some help with **how** to query it. flaqes focuses on **why** it matters.

### Traditional Tools vs flaqes

| Traditional Schema Tools | flaqes |
|-------------------------|---------|
| Lists tables and columns | ✅ Plus semantic meaning (FACT, DIMENSION, etc.) |
| Shows foreign keys | ✅ Plus relationship patterns (polymorphic, SCD, etc.) |
| Validates constraints | ✅ Plus trade-off analysis (what you gain, what you risk) |
| Enforces "best practices" | ✅ Provides context-aware recommendations |
| Binary pass/fail | ✅ Confidence scores with supporting evidence |

### Key Principles

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

## Documentation

### Intent Specification

The `Intent` dataclass captures your workload characteristics:

```python
from flaqes import Intent

intent = Intent(
    workload="OLTP" | "OLAP" | "mixed",
    write_frequency="high" | "medium" | "low",
    read_patterns=["point_lookup", "range_scan", "aggregation", "join_heavy"],
    consistency="strong" | "eventual",
    evolution_rate="high" | "medium" | "low" | "frozen",
    data_volume="small" | "medium" | "large" | "massive",
)
```

Common presets are available:

```python
from flaqes.core.intent import (
    OLTP_INTENT,
    OLAP_INTENT,
    EVENT_SOURCING_INTENT,
    STARTUP_MVP_INTENT,
)
```

### Modular API - Mix and Match

For custom analysis workflows, use individual analyzers:

```python
from flaqes import introspect_schema
from flaqes.analysis import RoleDetector, PatternDetector, TensionAnalyzer

# WHAT: Just introspect the schema
graph = await introspect_schema("postgresql://localhost/mydb")

# HOW: Run individual pattern/role detectors
role_detector = RoleDetector()
pattern_detector = PatternDetector()

for table in graph:
    role_result = role_detector.detect(table, graph)
    print(f"{table.name}: {role_result.primary_role.name}")

# WHY: Add tension analysis only when needed
from flaqes.core.intent import OLAP_INTENT
tension_analyzer = TensionAnalyzer(intent=OLAP_INTENT)
tensions = tension_analyzer.analyze(graph)
```

## Architecture

flaqes operates in three layers:

1. **Structural Facts Layer** (Objective)
   - Introspects database catalogs
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

**Version:** 0.1.0 (Alpha)

### Completed ✅
- ✅ PostgreSQL introspection
- ✅ Role detection (fact, dimension, event, junction, etc.)
- ✅ Pattern matching (SCD, soft delete, polymorphic, audit, etc.)
- ✅ Tension analysis (normalization, performance, evolution)
- ✅ Report generation (Markdown, JSON)
- ✅ Comprehensive test suite
- ✅ Command-line interface

### Roadmap 🚧
- [ ] DDL parsing for offline analysis
- [ ] MySQL support
- [ ] SQLite support
- [ ] Historical schema tracking
- [ ] LLM integration for natural language explanations

## Requirements

- Python 3.10+
- PostgreSQL 12+ (for database introspection)
- asyncpg (installed with `flaqes[postgresql]`)

## Contributing

Contributions welcome! This is an early-stage project. See [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for architecture details.

## License

MIT License - see LICENSE file for details

## Acknowledgments

Inspired by the need for thoughtful schema review tools that understand context and trade-offs rather than enforcing rigid "best practices."

---

**Note:** flaqes is alpha software. The API may change in future versions. Use in production with caution.
