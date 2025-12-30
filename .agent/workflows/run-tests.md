---
description: Run the test suite with coverage
---

# Run Tests

// turbo-all

1. Run pytest with coverage:
```bash
uv run pytest --cov=flakes --cov-report=term-missing -v
```

2. If tests fail, fix the issues before proceeding.

3. Ensure coverage is above 90% for core modules.