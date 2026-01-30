# Evolutionary Database Design: Implementation Plan

> **Goal:** Transform `flaqes` from a static snapshot analyzer into a time-aware architectural evolution tool.

## 1. Vision: "Git for Database Architecture"

Current database tools fall into two buckets:
1.  **Migration Managers** (Alembic, Flyway): Focus on *applying* changes safely. "How do I get from A to B?"
2.  **Schema Linters/Analyzers** (flaqes, squawk): Focus on the *current state*. "Is state A good?"

**Evolutionary Design** bridges the gap. It answers:
- "When did we lose distinct Fact/Dimension separation?"
- "Which migration introduced the performance regression in the `orders` table?"
- "How has our 'Design Tension' score trended over the last 6 months?"

## 2. Core Concepts

### 2.1. The Timeline (Barmaid Integration)
We leverage **Barmaid** to understand the Directed Acyclic Graph (DAG) of revisions.
- **Node**: A specific schema state (Revision ID).
- **Edge**: A migration (Delta).

### 2.2. The Snapshot (Offline Reconstruction)
We avoid the need for a live database by combining Alembic's SQL generation with Flaqes' DDL parser.
- **Input**: Alembic migration scripts.
- **Process**: `alembic upgrade :<rev> --sql` → Generates generic SQL from base to revision.
- **Output**: `SchemaGraph` object representing the database structure at that point in time.

### 2.3. The Architectural Diff
We compute the semantic difference between two `SchemaGraph` objects, not just the text diff.
- **Structural Diff**: Added/Removed tables/columns (standard).
- **Semantic Diff**: "Role Drift" (e.g., Table shifted from *Dimension* to *Fact*).
- **Tension Diff**: "New Tension Detected: Missing Index on FK (Critical)".

## 3. Architecture

```mermaid
flowchart TD
    subgraph "History Layer (Barmaid)"
        A[Alembic Folder] --> |Parse| B[Migration DAG]
        B --> |Select Path| C[Revision List]
    end

    subgraph "Reconstruction Layer (Alembic + Flaqes)"
        C --> |1. Generate SQL via Alembic| D[Raw DDL Stream]
        D --> |2. Parse DDL| E[SchemaGraph (Rev X)]
        D --> |2. Parse DDL| F[SchemaGraph (Rev Y)]
    end

    subgraph "Evolution Engine"
        E & F --> G[DiffEngine]
        G --> H[SchemaDelta]
        H --> I[EvolutionReport]
    end
```

## 4. New Data Structures

### `SchemaDelta`
Represents the architectural change between two revisions.

```python
@dataclass
class SchemaDelta:
    source_rev: str
    target_rev: str
    
    # Structural Changes
    added_tables: list[Table]
    removed_tables: list[str]
    modified_tables: list[TableModification]
    
    # Semantic Changes using flaqes analysis
    role_drifts: list[RoleDrift]  # e.g., orders: DIMENSION -> FACT
    tension_changes: list[TensionChange] # e.g., +2 Critical Tensions
```

### `RoleDrift`
```python
@dataclass
class RoleDrift:
    table: str
    old_role: RoleType
    new_role: RoleType
    confidence_delta: float
    reason: str  # e.g., "Added timestamp and high-cardinality FKs"
```

## 5. Implementation Phases

### Phase 1: The Wayback Machine (Snapshotting)
**Goal:** Ability to run `flaqes analyze` on any past revision.
- [x] Requirements: `alembic` installed.
- [x] Implement `SnapshotEngine`: Wraps `alembic.config.Config` to run offline SQL generation.
- [x] CLI: `flaqes analyze-rev <rev_id>`

### Phase 2: The Comparison Engine (Diffing)
**Goal:** Compare two revisions and output a text diff.
- [x] Implement `DiffEngine.compute(graph_a, graph_b) -> SchemaDelta`.
- [x] CLI: `flaqes diff <base_rev> <head_rev>`
- [x] Output:
  ```text
  [+] Table: user_logs (FACT - 0.95)
      --> Adds High-Volume Data Concern
  [~] Table: users
      --> Role Drift: CONFIG -> DIMENSION (Added 5 descriptive columns)
  ```

### Phase 3: The Evolution Report (Trends)
**Goal:** Visualize trends over a range of migrations.
- [x] CLI: `flaqes evolution`
- [x] ASCII Sparklines for metrics (Table Count).
- [ ] "Blame" View: Identify which update caused a tension. (Moved to future scope)

## 6. CLI Experience

## 6. CLI Experience

### 6.1. Analyze Past State
```bash
# Analyze schema as it looked in revision 1a2b3c
$ flaqes analyze --revision 1a2b3c
```

### 6.2. Compare Revisions
```bash
# Compare local HEAD against main branch origin
$ flaqes diff base head
# OR
$ flaqes diff 1a2b3c 4d5e6f
```

### 6.3. Evolution Summary
```bash
$ flaqes evolution
Graph: base --> ... --> 4d5e6f (current)

Step 1: 1a2b3c (Add Users)
  - Tables: +1
  - Tensions: 0

Step 2: 8g9h0i (Add Logs)
  - Tables: +1 (FACT)
  - Tensions: +1 (Missing Partitioning on Fact Table)
```

## 7. Technical Risks & Mitigations

| Risk                   | Mitigation                                                                                                                                                                                                                                            |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Alembic Dependency** | Make this feature an optional extra (`pip install flaqes[evolution]`).                                                                                                                                                                                |
| **SQL Dialects**       | `alembic upgrade --sql` produces distinct dialects. Flaqes DDL parser must handle or strip dialect-specific syntax (Postgres focus first).                                                                                                            |
| **Performance**        | Replaying 500 migrations to analyze `head` is slow. **Optimization**: Only replay from the nearest "checkpoint" or generate full DDL from `schema.dump` if available, then apply delta. For MVP: Replay from base is acceptable for offline analysis. |
