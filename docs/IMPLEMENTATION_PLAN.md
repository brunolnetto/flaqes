# flakes Implementation Plan

> **Version:** 0.1.0-alpha  
> **Created:** 2025-12-29  
> **Last Updated:** 2025-12-29  
> **Status:** ✅ Alpha Release Ready

## 1. Vision

**flakes** is a Python library that acts as a *schema critic* — not a validator or linter, but a tool that:

- **Explains** why a database structure is the way it is
- **Surfaces trade-offs** inherent in the current design
- **Proposes alternatives** optimized for different goals

The key differentiator: **understanding intent before giving advice**.

---

## 2. Non-Goals (Explicit Constraints)

| ❌ What flakes is NOT | Why |
|------------------------|-----|
| Migration tool | Combinatorially complex, already solved by Alembic/Flyway |
| Schema formatter | Cosmetic, low value |
| SQL linter | Syntax-level, not design-level |
| Automatic refactoring | Too opinionated, dangerous without human review |

flakes **analyzes and reasons**. It never mutates.

---

## 3. Mental Model: Three Layers

### Layer 1: Structural Facts (Objective, Deterministic)

Things derived with 100% confidence from schema introspection:

- Primary/Foreign key graph
- Column types, nullability, defaults
- Constraints (unique, check, exclusion)
- Indexes and their types
- Functional dependencies (declared via constraints)
- Table-to-table relationships and cardinalities

### Layer 2: Semantic Heuristics (Probabilistic, Pattern-Based)

Inferred patterns based on naming conventions and structural signals:

| Pattern | Signals |
|---------|---------|
| **Fact table** | High column count, FK-heavy, timestamps, numeric measures |
| **Dimension table** | Few FKs pointing to it, descriptive columns, low cardinality hints |
| **Event log** | Append-only signals, `created_at` without `updated_at`, no updates expected |
| **SCD Type 2** | `valid_from`, `valid_to`, `is_current` columns |
| **Soft delete** | `deleted_at` or `is_deleted` columns |
| **Polymorphic bucket** | `type` discriminator column, sparse nullable columns |
| **Junction table** | Composite PK of two FKs, minimal additional columns |

### Layer 3: Intent Axes (User-Provided)

Without intent, analysis is meaningless. Required input:

```python
@dataclass
class Intent:
    workload: Literal["OLTP", "OLAP", "mixed"]
    write_frequency: Literal["high", "medium", "low"]
    read_patterns: list[Literal["point_lookup", "range_scan", "aggregation", "join_heavy"]]
    consistency: Literal["strong", "eventual"]
    evolution_rate: Literal["high", "medium", "low", "frozen"]
    data_volume: Literal["small", "medium", "large", "massive"]  # rows estimate
    engine: Literal["postgresql", "mysql", "sqlite"]  # v1: postgresql only
```

---

## 4. Core Data Model

### 4.1 Schema Graph (Raw Layer)

```
SchemaGraph
├── tables: dict[str, Table]
├── relationships: list[Relationship]
└── indexes: list[Index]

Table
├── name: str
├── schema: str
├── columns: list[Column]
├── primary_key: PrimaryKey | None
├── foreign_keys: list[ForeignKey]
├── constraints: list[Constraint]
└── comment: str | None

Column
├── name: str
├── data_type: DataType
├── nullable: bool
├── default: str | None
├── is_generated: bool
└── comment: str | None

Relationship
├── source_table: str
├── target_table: str
├── foreign_key: ForeignKey
├── cardinality: Cardinality  # one-to-one, one-to-many, many-to-many
└── is_identifying: bool  # FK is part of PK

Index
├── name: str
├── table: str
├── columns: list[str]
├── is_unique: bool
├── is_partial: bool
├── method: str  # btree, hash, gin, gist, etc.
```

### 4.2 Table Role (Semantic Layer)

```
TableRole
├── hypothesis: RoleType  # fact, dimension, event, snapshot, junction, config, etc.
├── confidence: float  # 0.0 - 1.0
├── signals: list[Signal]  # evidence supporting the hypothesis
└── alternative_roles: list[tuple[RoleType, float]]  # other possible interpretations
```

### 4.3 Design Tension (Advisory Layer)

```
DesignTension
├── id: str
├── category: TensionCategory  # normalization, performance, evolution, consistency
├── description: str
├── current_benefit: str
├── risk: str
├── breaking_point: str  # "when data volume > X" or "when write rate > Y"
├── severity: Severity  # info, warning, critical
└── alternatives: list[Alternative]

Alternative
├── description: str
├── trade_off: str
├── effort: Effort  # low, medium, high
└── example_ddl: str | None
```

---

## 5. Architecture

```
flakes/
├── __init__.py           # Public API
├── core/
│   ├── intent.py         # Intent dataclass and validation
│   ├── schema_graph.py   # SchemaGraph, Table, Column, etc.
│   └── types.py          # Enums, Literals, type aliases
├── introspection/
│   ├── base.py           # Abstract introspector interface
│   ├── postgresql.py     # PostgreSQL catalog introspection (asyncpg)
│   └── ddl_parser.py     # Parse CREATE TABLE statements
├── analysis/
│   ├── role_detector.py  # Infer table roles from structure
│   ├── pattern_matcher.py # Detect design patterns (SCD, soft delete, etc.)
│   └── tension_analyzer.py # Generate design tensions
├── patterns/
│   ├── base.py           # Abstract pattern interface
│   ├── temporal.py       # SCD, event sourcing, audit patterns
│   ├── normalization.py  # 1NF/2NF/3NF violations, denormalization
│   └── relational.py     # Junction tables, polymorphic associations
├── report/
│   ├── models.py         # Report data structures
│   ├── text.py           # Plain text/markdown output
│   └── json.py           # Structured JSON output
└── cli.py                # Command-line interface (future)
```

---

## 6. Phased Implementation

### Phase 0: Foundation (Complete ✅)
- [x] Project setup with `uv`
- [x] Define core type hierarchy (`core/types.py`)
- [x] Define Intent dataclass (`core/intent.py`)
- [x] Define SchemaGraph data model (`core/schema_graph.py`)

### Phase 1: PostgreSQL Introspection (Complete ✅)
- [x] Implement PostgreSQL catalog queries
- [x] Build SchemaGraph from live database
- [x] Extract relationships and cardinalities
- [x] Handle edge cases (partitioned tables, views, materialized views)

### Phase 2: Role Detection (Complete ✅)
- [x] Implement signal-based role detection
- [x] Fact table detection
- [x] Dimension table detection
- [x] Event log detection
- [x] Junction table detection
- [x] Confidence scoring

### Phase 3: Pattern Matching (Complete ✅)
- [x] Temporal patterns (SCD Type 1/2, event sourcing)
- [x] Soft delete pattern
- [x] Polymorphic association pattern
- [x] Audit column patterns
- [x] JSONB usage patterns

### Phase 4: Design Tension Analysis (Complete ✅)
- [x] Normalization tension detector
- [x] Performance tension detector (missing indexes, wide tables)
- [x] Evolution tension detector (rigid schemas, JSONB escape hatches)
- [x] Intent-aware severity scoring

### Phase 5: Reporting (Complete ✅)
- [x] Structured report generation
- [x] Markdown output
- [x] JSON output for tooling integration
- [x] Summary vs detailed views
- [x] Main API entry points (`analyze_schema`, `introspect_schema`)

### Phase 6: Polish (Partial ✅)
- [ ] CLI interface (next priority)
- [ ] DDL parsing (for offline analysis)
- [x] Documentation (README, examples, implementation plan)
- [x] Test suite (253 tests, 234 passing)
- [ ] PyPI release (pending CLI)

---

## 7. Key Design Decisions

### Decision 1: Async-First
**Choice:** Use `asyncpg` for PostgreSQL, async throughout.  
**Rationale:** Database introspection involves I/O. Async enables concurrent table analysis.

### Decision 2: No ORM Dependency
**Choice:** Work directly with database catalogs, not SQLAlchemy models.  
**Rationale:** SQLAlchemy metadata doesn't capture everything (comments, partial indexes, etc.). Direct catalog access is more complete.

### Decision 3: Intent Required for Analysis
**Choice:** Make Intent a required parameter for tension analysis.  
**Rationale:** Without knowing the workload, any recommendation is noise. Better to refuse than to spam generic advice.

### Decision 4: Confidence Scores, Not Binary Judgments
**Choice:** Every inference includes a confidence score.  
**Rationale:** Acknowledges uncertainty. Lets users filter by confidence threshold.

### Decision 5: Deterministic Core, Optional LLM Layer
**Choice:** Core analysis is pure Python. LLM integration (for explanations) is optional.  
**Rationale:** Reproducibility. Testability. No API key requirements for basic usage.

---

## 8. Example Usage (Target API)

```python
import asyncio
from flakes import analyze_schema, Intent

async def main():
    intent = Intent(
        workload="OLAP",
        write_frequency="medium",
        read_patterns=["aggregation", "range_scan"],
        consistency="eventual",
        evolution_rate="high",
        data_volume="large",
        engine="postgresql"
    )
    
    report = await analyze_schema(
        dsn="postgresql://user:pass@localhost/mydb",
        intent=intent,
        tables=["orders", "order_items", "customers"],  # optional filter
    )
    
    # High-level summary
    print(report.summary())
    
    # Detected table roles
    for table in report.tables:
        print(f"{table.name}: {table.role.hypothesis} ({table.role.confidence:.0%})")
    
    # Design tensions
    for tension in report.tensions:
        print(f"[{tension.severity}] {tension.description}")
        print(f"  Current benefit: {tension.current_benefit}")
        print(f"  Risk: {tension.risk}")
        print(f"  Breaking point: {tension.breaking_point}")

asyncio.run(main())
```

---

## 9. Open Questions

1. **Scope of "table neighbors"**: Should analysis include FK depth 1, depth 2, or configurable?
2. **Data sampling**: Should flakes optionally sample data to validate hypotheses (e.g., cardinality estimates)?
3. **Historical analysis**: Should flakes track schema changes over time?
4. **Multi-database support**: Priority of MySQL, SQLite after PostgreSQL?
5. **LLM integration**: Built-in optional module, or separate package (`flakes-llm`)?

---

## 10. Success Criteria for v0.1.0

- [x] Can introspect a PostgreSQL database
- [x] Can build a complete SchemaGraph
- [x] Can detect 3+ table roles with confidence scores (6 roles: fact, dimension, event, junction, lookup, entity)
- [x] Can detect 3+ design patterns (15+ patterns including SCD, soft delete, audit, polymorphic, etc.)
- [x] Can generate 3+ design tensions (normalization, performance, evolution tensions with alternatives)
- [x] Produces useful markdown report (with JSON export option)
- [x] Has test coverage for core functionality (253 tests total, 234 passing, 19 integration tests skipped)
- [x] Documentation with examples (README, implementation plan, completion summary, example script)

**Result: 8/8 criteria met ✅**

---

## 11. Implementation Summary

### What Was Built

**Core Components:**
- 16 Python modules, 4,582 lines of code
- Full type safety with Python 3.13+ and strict mypy
- Async-first architecture with asyncpg

**Analysis Pipeline:**
1. **Introspection Layer** - PostgreSQL catalog queries via asyncpg
2. **Role Detection** - Signal-based inference with confidence scores
3. **Pattern Matching** - 15+ design patterns with evidence tracking
4. **Tension Analysis** - Intent-aware design trade-off detection
5. **Reporting** - Markdown and JSON output with summaries

**Key Features Delivered:**
- `analyze_schema()` - End-to-end analysis API
- `introspect_schema()` - Lower-level schema graph extraction
- Intent dataclass with common presets (OLTP, OLAP, event sourcing, MVP)
- Comprehensive test suite with 234 passing tests
- Professional documentation and examples

### Project Structure (Actual)

```
flakes/
├── __init__.py              # Public API exports
├── api.py                   # Main entry points (NEW)
├── core/
│   ├── intent.py            # Intent specification
│   ├── schema_graph.py      # Data model (461 lines)
│   └── types.py             # Type definitions
├── introspection/
│   ├── base.py              # Abstract interface
│   ├── postgresql.py        # PostgreSQL implementation (800+ lines)
│   └── registry.py          # Engine registry
├── analysis/
│   ├── role_detector.py     # Table role detection
│   ├── pattern_matcher.py   # Pattern recognition
│   └── tension_analyzer.py  # Tension analysis
├── patterns/                # Pattern library (extensible)
└── report/
    └── __init__.py          # Report generation (260 lines)

tests/                       # 253 test cases
docs/                        # Documentation
examples/                    # Usage examples
```

### Next Development Priorities

**Phase 6 Completion:**
1. CLI interface (2-3 hours) - `flakes analyze postgresql://...`
2. PyPI publishing (1 hour) - Make installable
3. CI/CD setup (1-2 hours) - GitHub Actions for tests

**Future Enhancements:**
- DDL parser for offline analysis
- MySQL and SQLite support
- Historical schema tracking
- LLM integration for natural language explanations
- Schema diffing between versions
- Performance benchmarking suite

---

*Document created: 2025-12-29*  
*Status updated: 2025-12-29*  
*Current version: 0.1.0-alpha (ready for real-world testing)*
