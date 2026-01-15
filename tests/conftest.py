"""Pytest configuration and shared fixtures."""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires Docker)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: tests that require external services (Docker, databases)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip integration tests by default unless --run-integration or -m integration."""
    # Check if we're running integration tests specifically
    marker_expr = config.getoption("-m", default="")
    run_integration = getattr(config.option, "run_integration", False)
    
    if run_integration or marker_expr == "integration":
        # Don't skip integration tests
        return
    
    # Skip integration tests by default
    skip_integration = pytest.mark.skip(
        reason="Integration tests skipped. Run with: --run-integration or -m integration"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(scope="session")
def shared_postgres_dsn():
    """Start a shared PostgreSQL container for all integration tests.
    
    This fixture is session-scoped, meaning the container starts once
    and is reused across all test files, significantly speeding up tests.
    """
    try:
        from testcontainers.postgres import PostgresContainer
        import subprocess
    except ImportError:
        pytest.skip("testcontainers[postgres] not installed")

    # Start container
    with PostgresContainer("postgres:16-alpine") as postgres:
        host = postgres.get_container_host_ip()
        port = postgres.get_exposed_port(5432)
        user = postgres.username
        password = postgres.password
        database = postgres.dbname
        
        dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        
        # We'll return the container object and DSN so tests can run psql commands if needed
        # But for simplicity, let's just return the DSN and helper to exec SQL
        
        class PostgresContext:
            def __init__(self, dsn, container):
                self.dsn = dsn
                self.container = container
            
            def run_sql(self, sql: str):
                container_id = self.container.get_wrapped_container().id
                subprocess.run(
                    ["docker", "exec", "-i", container_id, "psql", "-U", user, "-d", database],
                    input=sql,
                    capture_output=True,
                    text=True,
                    check=True,
                )
        
        yield PostgresContext(dsn, postgres)
