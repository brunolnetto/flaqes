---
description: How to add a new schema pattern detector
---

# Add a New Pattern Detector

When adding a new pattern detector (e.g., detecting SCD Type 2 tables):

## 1. Define the Pattern

In `flaqes/patterns/`, create or update the appropriate module:
- `temporal.py` for time-related patterns
- `normalization.py` for normalization patterns  
- `relational.py` for relationship patterns
- Create a new file if none fit

## 2. Implement the Detector

```python
from flaqes.core.schema_graph import Table
from flaqes.patterns.base import PatternMatch, PatternDetector

class SCDType2Detector(PatternDetector):
    """Detects Slowly Changing Dimension Type 2 patterns."""
    
    pattern_id = "scd_type_2"
    pattern_name = "SCD Type 2"
    
    def detect(self, table: Table) -> PatternMatch | None:
        # Look for signals:
        # - valid_from / valid_to columns
        # - is_current boolean
        # - Composite key including validity period
        
        signals = []
        confidence = 0.0
        
        # ... detection logic ...
        
        if confidence > 0.5:
            return PatternMatch(
                pattern_id=self.pattern_id,
                table=table.name,
                confidence=confidence,
                signals=signals,
            )
        return None
```

## 3. Register the Detector

Add to `flaqes/patterns/__init__.py`:
```python
from .temporal import SCDType2Detector

DEFAULT_DETECTORS = [
    # ... existing detectors ...
    SCDType2Detector(),
]
```

## 4. Write Tests

Create `tests/patterns/test_scd_type2.py`:
```python
def test_detects_scd_type2_with_valid_from_to():
    table = make_table(columns=[
        Column("id", "integer"),
        Column("valid_from", "timestamp"),
        Column("valid_to", "timestamp"),
        Column("is_current", "boolean"),
    ])
    
    detector = SCDType2Detector()
    match = detector.detect(table)
    
    assert match is not None
    assert match.confidence > 0.8
```

## 5. Document

Update `docs/patterns.md` with:
- Pattern description
- Signals that trigger detection
- Example schemas
- Known limitations
