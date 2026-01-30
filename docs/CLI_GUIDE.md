# flakes CLI Usage Guide

The `flakes` command-line tool provides easy access to database schema analysis.

## Installation

After installing flakes, the `flakes` command will be available in your environment:

```bash
pip install flakes[postgresql]
```

## Quick Start

```bash
# Analyze entire database
flakes analyze postgresql://user:pass@localhost/mydb

# Save report to file
flakes analyze --output report.md postgresql://localhost/mydb

# Use OLAP intent preset
flakes analyze --intent olap postgresql://localhost/mydb

# Analyze specific tables
flakes analyze --tables users,orders,products postgresql://localhost/mydb
```

## Commands

### `flakes analyze`

Analyze a database schema and generate a report.

**Basic Syntax:**
```bash
flakes analyze [OPTIONS] DSN
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
flakes analyze --intent oltp postgresql://localhost/mydb

# OLAP workload (data warehouses, analytics)
flakes analyze --intent olap postgresql://localhost/mydb

# Event sourcing workload
flakes analyze --intent event-sourcing postgresql://localhost/mydb

# Startup MVP (flexible, evolving schema)
flakes analyze --intent startup-mvp postgresql://localhost/mydb
```

### Custom Intent

Build a custom intent with individual parameters:

```bash
flakes analyze \
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
flakes analyze --tables users postgresql://localhost/mydb

# Multiple tables
flakes analyze --tables users,orders,products postgresql://localhost/mydb
```

### Filter by Schema

```bash
# Specific schemas
flakes analyze --schemas public,analytics postgresql://localhost/mydb
```

### Exclude Patterns

```bash
# Exclude temporary and test tables
flakes analyze --exclude "tmp_*,test_*,staging_*" postgresql://localhost/mydb
```

## Output Options

### Output Format

```bash
# Markdown (default)
flakes analyze postgresql://localhost/mydb

# JSON for programmatic use
flakes analyze --format json postgresql://localhost/mydb
```

### Save to File

```bash
# Save markdown report
flakes analyze --output report.md postgresql://localhost/mydb

# Save JSON report
flakes analyze --format json --output report.json postgresql://localhost/mydb
```

### Verbosity

```bash
# Quiet mode (summary only to stderr, report to stdout)
flakes analyze --quiet postgresql://localhost/mydb

# Verbose mode (detailed error messages)
flakes analyze --verbose postgresql://localhost/mydb
```

## Examples

### Example 1: Production OLTP Database

```bash
flakes analyze \
  --intent oltp \
  --output prod-analysis.md \
  postgresql://readonly:password@prod.example.com/myapp
```

### Example 2: Data Warehouse with Custom Intent

```bash
flakes analyze \
  --workload OLAP \
  --write-frequency low \
  --read-patterns aggregation,range_scan \
  --data-volume massive \
  --output warehouse-report.md \
  postgresql://analyst@warehouse.local/dwh
```

### Example 3: Analyze Specific Tables as JSON

```bash
flakes analyze \
  --tables users,sessions,events \
  --format json \
  --output core-tables.json \
  postgresql://localhost/mydb
```

### Example 4: Exclude Test Data

```bash
flakes analyze \
  --exclude "test_*,tmp_*,_backup_*" \
  --quiet \
  postgresql://localhost/development
```

### Example 5: Quick Check with Summary

```bash
flakes analyze --intent olap --quiet postgresql://localhost/mydb 2>&1 | grep "Summary"
```

## Using with Docker

If your database is in Docker:

```bash
# Connect to Docker container
flakes analyze postgresql://user:pass@localhost:5432/dbname

# Use Docker network
docker run --network mynetwork \
  -v $(pwd):/output \
  flakes:latest \
  analyze --output /output/report.md \
  postgresql://db-container/mydb
```

## Environment Variables

You can use environment variables for sensitive information:

```bash
# Set database connection
export DATABASE_URL="postgresql://user:pass@host/db"

# Use in command
flakes analyze $DATABASE_URL
```

## Exit Codes

- `0`: Success
- `1`: Error (connection failed, analysis error)
- `130`: Interrupted (Ctrl+C)

## Tips

1. **Use Read-Only Credentials**: flakes only reads, but use read-only database users for safety
2. **Large Databases**: Use `--tables` to analyze incrementally
3. **CI/CD Integration**: Use `--format json` for automated processing
4. **Compare Environments**: Run on dev/staging/prod to compare design tensions

## Troubleshooting

### Connection Issues

```bash
# Test connection first
psql "postgresql://user:pass@host/db" -c "SELECT 1"

# Then run flakes
flakes analyze postgresql://user:pass@host/db
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
flakes analyze "postgresql://user:pass@host/db?sslmode=require"
```

## Version Information

```bash
flakes version
```

## Getting Help

```bash
# General help
flakes --help

# Command-specific help
flakes analyze --help
```

## See Also

- [README.md](../README.md) - Project overview and Python API
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - Architecture details
- [examples/](../examples/) - Python API examples
