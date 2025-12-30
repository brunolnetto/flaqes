"""Test the main API entry point."""

import pytest

from flaqes.api import analyze_schema, introspect_schema


@pytest.mark.asyncio
async def test_analyze_schema_api_basic():
    """Test that analyze_schema function exists and has correct signature."""
    # Just verify the function is importable and callable
    assert callable(analyze_schema)
    assert callable(introspect_schema)


@pytest.mark.asyncio
async def test_introspect_schema_api():
    """Test introspect_schema with mock data."""
    # This would require a real database or mocking
    # For now, just verify the function signature
    import inspect

    sig = inspect.signature(introspect_schema)
    assert "dsn" in sig.parameters
    assert "tables" in sig.parameters
    assert "schemas" in sig.parameters


@pytest.mark.asyncio
async def test_analyze_schema_api_signature():
    """Test analyze_schema has correct signature."""
    import inspect

    sig = inspect.signature(analyze_schema)
    assert "dsn" in sig.parameters
    assert "intent" in sig.parameters
    assert "tables" in sig.parameters
    assert "schemas" in sig.parameters
    assert "exclude_patterns" in sig.parameters
