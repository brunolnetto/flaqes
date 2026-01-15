"""Integration tests for the API module using testcontainers.

These tests verify the analyze_schema and introspect_schema functions
work correctly with a real PostgreSQL database.
"""

import subprocess

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


TEST_SCHEMA_SQL = """
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    body TEXT,
    status VARCHAR(20) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_posts_user ON posts(user_id);

INSERT INTO users (email, name) VALUES ('alice@example.com', 'Alice');
ANALYZE;
"""


@pytest.fixture(scope="module")
def postgres_dsn(shared_postgres_dsn):
    """Reuse shared PostgreSQL container and return connection URL."""
    # Clean up and setup
    cleanup_sql = "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    shared_postgres_dsn.run_sql(cleanup_sql)
    shared_postgres_dsn.run_sql(TEST_SCHEMA_SQL)
    
    return shared_postgres_dsn.dsn


class TestAnalyzeSchema:
    """Tests for analyze_schema function."""

    @pytest.mark.asyncio
    async def test_analyze_schema_basic(self, postgres_dsn: str) -> None:
        """Test basic schema analysis."""
        from flaqes import analyze_schema
        
        report = await analyze_schema(postgres_dsn)
        
        assert report is not None
        assert report.table_count >= 2
        assert "users" in [t.split(".")[-1] for t in report.table_roles.keys()]

    @pytest.mark.asyncio
    async def test_analyze_schema_with_intent(self, postgres_dsn: str) -> None:
        """Test schema analysis with intent."""
        from flaqes import analyze_schema, Intent
        
        intent = Intent(
            workload="OLTP",
            write_frequency="high",
            data_volume="small",
        )
        
        report = await analyze_schema(postgres_dsn, intent=intent)
        
        assert report is not None
        assert report.intent is not None
        assert report.intent.workload == "OLTP"
        
        # Report should have markdown output
        markdown = report.to_markdown()
        assert "Schema Analysis Report" in markdown
        
        # Report should have JSON output
        json_data = report.to_dict()
        assert "table_count" in json_data


class TestIntrospectSchema:
    """Tests for introspect_schema function."""

    @pytest.mark.asyncio
    async def test_introspect_schema_basic(self, postgres_dsn: str) -> None:
        """Test basic schema introspection."""
        from flaqes import introspect_schema
        
        graph = await introspect_schema(postgres_dsn)
        
        assert graph is not None
        tables = list(graph)
        assert len(tables) >= 2
        
        # Check users table
        users = graph.get_table_by_name("users")
        assert users is not None
        assert len(users.columns) >= 4
        assert users.primary_key is not None
        
        # Check posts table  
        posts = graph.get_table_by_name("posts")
        assert posts is not None
        assert len(posts.foreign_keys) >= 1
