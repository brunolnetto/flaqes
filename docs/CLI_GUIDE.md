# flaqes CLI Usage Guide

The `flaqes` command-line tool provides easy access to database schema analysis.

## Installation

After installing flaqes, the `flaqes` command will be available in your environment:

```bash
pip install flaqes[postgresql]
```

## Quick Start

```bash
# Analyze entire database
flaqes analyze postgresql://user:pass@localhost/mydb

# Save report to file
flaqes analyze --output report.md postgresql://localhost/mydb

# Use OLAP intent preset
flaqes analyze --intent olap postgresql://localhost/mydb

# Analyze specific tables
flaqes analyze --tables users,orders,products postgresql://localhost/mydb
```

## Commands

### `flaqes analyze`

Analyze a database schema and generate a report.

**Basic Syntax:**
```bash
flaqes analyze [OPTIONS] DSN
```

**DSN Format:**
```
postgresql://[user[:password]@][host][:port][/database]
```

## Intent Options

### Preset Intents

Use predefined intent profiles optimized for common scenarios:

```bash
# OLTP workload (transactional applications)
flaqes analyze --intent oltp postgresql://localhost/mydb

# OLAP workload (data warehouses, analytics)
flaqes analyze --intent olap postgresql://localhost/mydb

# Event sourcing workload
flaqes analyze --intent event-sourcing postgresql://localhost/mydb

# Startup MVP (flexible, evolving schema)
flaqes analyze --intent startup-mvp postgresql://localhost/mydb
```

### Custom Intent

Build a custom intent with individual parameters:

```bash
flaqes analyze \
  --workload OLTP \
  --write-frequency high \
  --read-patterns point_lookup,join_heavy \
  --consistency strong \
  --evolution-rate high \
  --data-volume medium \
  postgresql://localhost/mydb
```

**Intent Parameters:**

- `--workload`: `OLTP`, `OLAP`, or `mixed`
- `--write-frequency`: `high`, `medium`, or `low`
- `--read-patterns`: Comma-separated list of:
  - `point_lookup` - Single row lookups by key
  - `range_scan` - Range queries
  - `aggregation` - GROUP BY, SUM, AVG operations
  - `join_heavy` - Complex multi-table joins
- `--consistency`: `strong` or `eventual`
- `--evolution-rate`: `high`, `medium`, `low`, or `frozen`
- `--data-volume`: `small`, `medium`, `large`, or `massive`

## Filtering Options

### Analyze Specific Tables

```bash
# Single table
flaqes analyze --tables users postgresql://localhost/mydb

# Multiple tables
flaqes analyze --tables users,orders,products postgresql://localhost/mydb
```

### Filter by Schema

```bash
# Specific schemas
flaqes analyze --schemas public,analytics postgresql://localhost/mydb
```

### Exclude Patterns

```bash
# Exclude temporary and test tables
flaqes analyze --exclude "tmp_*,test_*,staging_*" postgresql://localhost/mydb
```

## Output Options

### Output Format

```bash
# Markdown (default)
flaqes analyze postgresql://localhost/mydb

# JSON for programmatic use
flaqes analyze --format json postgresql://localhost/mydb
```

### Save to File

```bash
# Save markdown report
flaqes analyze --output report.md postgresql://localhost/mydb

# Save JSON report
flaqes analyze --format json --output report.json postgresql://localhost/mydb
```

### Verbosity

```bash
# Quiet mode (summary only to stderr, report to stdout)
flaqes analyze --quiet postgresql://localhost/mydb

# Verbose mode (detailed error messages)
flaqes analyze --verbose postgresql://localhost/mydb
```

## Examples

### Example 1: Production OLTP Database

```bash
flaqes analyze \
  --intent oltp \
  --output prod-analysis.md \
  postgresql://readonly:password@prod.example.com/myapp
```

### Example 2: Data Warehouse with Custom Intent

```bash
flaqes analyze \
  --workload OLAP \
  --write-frequency low \
  --read-patterns aggregation,range_scan \
  --data-volume massive \
  --output warehouse-report.md \
  postgresql://analyst@warehouse.local/dwh
```

### Example 3: Analyze Specific Tables as JSON

```bash
flaqes analyze \
  --tables users,sessions,events \
  --format json \
  --output core-tables.json \
  postgresql://localhost/mydb
```

### Example 4: Exclude Test Data

```bash
flaqes analyze \
  --exclude "test_*,tmp_*,_backup_*" \
  --quiet \
  postgresql://localhost/development
```

### Example 5: Quick Check with Summary

```bash
flaqes analyze --intent olap --quiet postgresql://localhost/mydb 2>&1 | grep "Summary"
```

## Using with Docker

If your database is in Docker:

```bash
# Connect to Docker container
flaqes analyze postgresql://user:pass@localhost:5432/dbname

# Use Docker network
docker run --network mynetwork \
  -v $(pwd):/output \
  flaqes:latest \
  analyze --output /output/report.md \
  postgresql://db-container/mydb
```

## Environment Variables

You can use environment variables for sensitive information:

```bash
# Set database connection
export DATABASE_URL="postgresql://user:pass@host/db"

# Use in command
flaqes analyze $DATABASE_URL
```

## Exit Codes

- `0`: Success
- `1`: Error (connection failed, analysis error)
- `130`: Interrupted (Ctrl+C)

## Tips

1. **Use Read-Only Credentials**: flaqes only reads, but use read-only database users for safety
2. **Large Databases**: Use `--tables` to analyze incrementally
3. **CI/CD Integration**: Use `--format json` for automated processing
4. **Compare Environments**: Run on dev/staging/prod to compare design tensions

## Troubleshooting

### Connection Issues

```bash
# Test connection first
psql "postgresql://user:pass@host/db" -c "SELECT 1"

# Then run flaqes
flaqes analyze postgresql://user:pass@host/db
```

### Permission Issues

Ensure the database user has SELECT permissions on system catalogs:

```sql
GRANT SELECT ON ALL TABLES IN SCHEMA information_schema TO myuser;
GRANT SELECT ON ALL TABLES IN SCHEMA pg_catalog TO myuser;
```

### SSL Connections

For SSL connections, add SSL parameters to the DSN:

```bash
flaqes analyze "postgresql://user:pass@host/db?sslmode=require"
```

## Version Information

```bash
flaqes version
```

## Getting Help

```bash
# General help
flaqes --help

# Command-specific help
flaqes analyze --help
```

## See Also

- [README.md](../README.md) - Project overview and Python API
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - Architecture details
- [examples/](../examples/) - Python API examples
