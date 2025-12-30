# flaqes Project Principles

## Core Philosophy

**flaqes is a schema critic, not a schema cop.**

We explain trade-offs, not enforce rules. We surface tensions, not errors. We propose alternatives, not mandates.

---

## The Three Laws

### 1. Never Recommend Without Intent

Without knowing the workload, evolution rate, and consistency requirements, any advice is noise. If intent is missing, we either:
- Refuse to analyze (strict mode), or
- Output with heavy caveats and low confidence (permissive mode)

**We do not spam "best practices" detached from context.**

### 2. Trade-offs Over Judgments

Bad output:
> "Consider normalizing this table."

Good output:
> "This table mixes entity state and event history. Current design favors write simplicity. If you expect frequent point lookups of current state, splitting into `entity_current` + `entity_events` would reduce query complexity at the cost of duplication."

**Every finding must articulate what the current design optimizes for, what it sacrifices, and when it breaks.**

### 3. Confidence, Not Certainty

Every inference includes a confidence score. We acknowledge:
- Structural facts (from catalog) = 100% confidence
- Semantic heuristics (from patterns) = probabilistic
- Design tensions (from intent mismatch) = contextual

**We let users filter by confidence threshold. We don't pretend to know more than we do.**

---

## Technical Principles

### Async-First
All I/O operations are async. Database introspection happens concurrently where possible.

### No ORM Lock-in
We introspect database catalogs directly, not ORM metadata. This gives us:
- Full information (comments, partial indexes, expression indexes)
- Engine-specific features
- No dependency on user's ORM choice

### Deterministic Core
The analysis engine is pure Python with no external API calls. Results are reproducible and testable. LLM integration is an optional presentation layer, not the brain.

### PostgreSQL First
v1.0 targets PostgreSQL exclusively. We go deep before going wide. Other engines come later.

---

## Code Conventions

### Type Everything
All public APIs use type hints. Use `dataclasses` for data structures, `Literal` for constrained strings, `Protocol` for interfaces.

### Prefer Composition
Small, focused functions. No god classes. The analyzer is a pipeline of transformations, not a monolith.

### Test the Boundaries
Unit test pattern detection. Integration test introspection against real PostgreSQL (via testcontainers). Don't mock what you can spin up.

### Document Why, Not What
Code comments explain rationale and trade-offs. The "what" should be obvious from well-named functions.

---

## Language & Naming

### User-Facing Terms
| Term | Meaning |
|------|---------|
| **Table Role** | The semantic purpose of a table (fact, dimension, event, etc.) |
| **Design Tension** | A trade-off inherent in the current structure |
| **Signal** | Evidence supporting a hypothesis about a table |
| **Intent** | User-declared goals for the schema |

### Code Naming
- `snake_case` for functions, variables, modules
- `PascalCase` for classes and type aliases
- Prefix abstract base classes with `Base` (e.g., `BaseIntrospector`)
- Suffix protocols with `Protocol` (e.g., `PatternMatcherProtocol`)

---

## What Success Looks Like

A senior database engineer uses flaqes and:
1. **Learns something new** about their own schema
2. **Disagrees with a finding** and articulates why — that's valuable friction
3. **Uses the output** in a design review or documentation

If flaqes produces output that gets blindly followed by juniors without understanding, we've failed.

---

## Anti-Patterns to Avoid

❌ Generic advice without context ("add an index")  
❌ Binary pass/fail scoring  
❌ Requiring an LLM for basic functionality  
❌ Mutating schemas automatically  
❌ Pretending confidence where none exists  
❌ Ignoring the user's stated intent  

---

*These principles guide every design decision. When in doubt, refer back here.*
