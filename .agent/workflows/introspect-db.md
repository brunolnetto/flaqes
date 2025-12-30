---
description: Test database introspection against a local PostgreSQL
---

# Introspect Database

1. Ensure PostgreSQL is running locally or via Docker:
```bash
docker run -d --name flaqes-test-pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=testdb -p 5432:5432 postgres:16
```

2. Run the introspection test script:
```bash
uv run python -m flaqes.cli introspect --dsn "postgresql://postgres:test@localhost/testdb"
```

3. Review the output for correctness.

4. Clean up:
```bash
docker stop flaqes-test-pg && docker rm flaqes-test-pg
```
