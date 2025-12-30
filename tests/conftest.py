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
