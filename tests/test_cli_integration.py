"""Integration tests for the CLI using testcontainers.

These tests verify the CLI works end-to-end with a real PostgreSQL database.
Requires Docker to be running.
"""

import subprocess
import tempfile

import pytest

# Check for required dependencies
try:
    import asyncpg
    from testcontainers.postgres import PostgresContainer
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

pytestmark = [
    pytest.mark.skipif(
        not HAS_DEPS,
        reason="testcontainers[postgres] or asyncpg not installed"
    ),
    pytest.mark.integration,
]


# Simple test schema
TEST_SCHEMA_SQL = """
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO users (email, name) VALUES ('test@example.com', 'Test User');
ANALYZE;
"""


@pytest.fixture(scope="module")
def postgres_container(shared_postgres_dsn):
    """Reuse shared PostgreSQL container and set up schema."""
    # Clean up and setup
    cleanup_sql = "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    shared_postgres_dsn.run_sql(cleanup_sql)
    shared_postgres_dsn.run_sql(TEST_SCHEMA_SQL)
    
    return shared_postgres_dsn.dsn


class TestCLIAnalyze:
    """Integration tests for the analyze command."""

    def test_analyze_markdown_output(self, postgres_container: str, capsys) -> None:
        """Test analyze with markdown output."""
        from flaqes.cli import main
        from unittest.mock import patch
        
        with patch("sys.argv", ["flaqes", "analyze", postgres_container]):
            result = main()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "Schema Analysis Report" in captured.out

    def test_analyze_json_output(self, postgres_container: str, capsys) -> None:
        """Test analyze with JSON output."""
        from flaqes.cli import main
        from unittest.mock import patch
        import json
        
        with patch("sys.argv", ["flaqes", "analyze", postgres_container, "--format", "json"]):
            result = main()
        
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "table_count" in data
        assert data["table_count"] >= 2

    def test_analyze_with_workload(self, postgres_container: str, capsys) -> None:
        """Test analyze with workload specification."""
        from flaqes.cli import main
        from unittest.mock import patch
        
        with patch("sys.argv", [
            "flaqes", "analyze", postgres_container,
            "--workload", "OLTP",
            "--volume", "small"
        ]):
            result = main()
        
        assert result == 0


class TestCLIIntrospect:
    """Integration tests for the introspect command."""

    def test_introspect_text_output(self, postgres_container: str, capsys) -> None:
        """Test introspect with text output."""
        from flaqes.cli import main
        from unittest.mock import patch
        
        with patch("sys.argv", ["flaqes", "introspect", "--dsn", postgres_container]):
            result = main()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "tables found" in captured.out
        assert "users" in captured.out.lower()

    def test_introspect_json_output(self, postgres_container: str, capsys) -> None:
        """Test introspect with JSON output."""
        from flaqes.cli import main
        from unittest.mock import patch
        import json
        
        with patch("sys.argv", [
            "flaqes", "introspect", "--dsn", postgres_container,
            "--format", "json"
        ]):
            result = main()
        
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "tables" in data
        assert len(data["tables"]) >= 2


class TestCLIAnalyzeDDL:
    """Integration tests for the analyze-ddl command."""

    def test_analyze_ddl_markdown(self, capsys) -> None:
        """Test analyze-ddl with markdown output."""
        from flaqes.cli import main
        from unittest.mock import patch
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("""
            CREATE TABLE products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                price NUMERIC,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """)
            f.flush()
            
            with patch("sys.argv", ["flaqes", "analyze-ddl", f.name]):
                result = main()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "Schema Analysis Report" in captured.out

    def test_analyze_ddl_json(self, capsys) -> None:
        """Test analyze-ddl with JSON output."""
        from flaqes.cli import main
        from unittest.mock import patch
        import json
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("""
            CREATE TABLE items (
                id SERIAL PRIMARY KEY,
                name TEXT
            );
            """)
            f.flush()
            
            with patch("sys.argv", ["flaqes", "analyze-ddl", f.name, "--format", "json"]):
                result = main()
        
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["table_count"] == 1
