# flakes 🔍

**A schema critic for PostgreSQL databases**

flakes analyzes database structures and surfaces design tensions, trade-offs, and alternative approaches based on your stated intent. Think of it as a thoughtful colleague who reviews your schema and explains *why* things are the way they are, not just *what* they are.

## Features

- 🎯 **Intent-Aware Analysis** - Provides contextual advice based on your workload (OLTP, OLAP, or mixed)
- 🔍 **Role Detection** - Identifies semantic roles (fact tables, dimensions, events, junctions, etc.) with confidence scores
- 🎨 **Pattern Recognition** - Detects design patterns like SCD Type 2, soft deletes, polymorphic associations, and more
- ⚖️ **Design Tensions** - Surfaces trade-offs in your current design with alternatives and effort estimates
- 📊 **Comprehensive Reports** - Generates structured reports in Markdown or JSON format
- 🔬 **No Mutations** - Analysis only, never modifies your database

## Installation

```bash
# Basic installation
pip install flakes

# With PostgreSQL support (required for v0.1)
pip install flakes[postgresql]

# Development installation
pip install flakes[dev]
```

Or using `uv`:

```bash
uv pip install flakes[postgresql]
```

## Quick Start

```python
import asyncio
from flakes import analyze_schema, Intent

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

## What Makes flakes Different?

Unlike traditional schema validators or linters, flakes:

1. **Understands Intent** - Recommendations depend on your workload. A denormalized table might be problematic for OLTP but perfect for OLAP.

2. **Embraces Uncertainty** - Every inference includes a confidence score and the signals that led to it. No black-box "best practices."

3. **Explains Trade-offs** - Instead of saying "this is wrong," flakes says "here's what you gain, here's what you risk, and here's when it might break."

4. **Never Mutates** - flakes is read-only. It analyzes and advises, never changes your database.

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
from flakes import Intent

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
from flakes.core.intent import (
    OLTP_INTENT,
    OLAP_INTENT,
    EVENT_SOURCING_INTENT,
    STARTUP_MVP_INTENT,
)
```

### Lower-Level API

For custom analysis workflows:

```python
from flakes import introspect_schema
from flakes.analysis import RoleDetector, PatternDetector, TensionAnalyzer

# Just introspect the schema
graph = await introspect_schema("postgresql://localhost/mydb")

# Run individual analyzers
role_detector = RoleDetector()
pattern_detector = PatternDetector()
tension_analyzer = TensionAnalyzer(intent=intent)

for table in graph:
    role_result = role_detector.detect(table, graph)
    print(f"{table.name}: {role_result.primary_role.name}")
```

## Architecture

flakes operates in three layers:

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

### Roadmap 🚧
- [ ] CLI interface (`flakes analyze postgresql://...`)
- [ ] DDL parsing for offline analysis
- [ ] MySQL support
- [ ] SQLite support
- [ ] Historical schema tracking
- [ ] LLM integration for natural language explanations

## Requirements

- Python 3.13+
- PostgreSQL 12+ (for database introspection)
- asyncpg (installed with `flakes[postgresql]`)

## Contributing

Contributions welcome! This is an early-stage project. See [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for architecture details.

## License

MIT License - see LICENSE file for details

## Acknowledgments

Inspired by the need for thoughtful schema review tools that understand context and trade-offs rather than enforcing rigid "best practices."

---

**Note:** flakes is alpha software. The API may change in future versions. Use in production with caution.
