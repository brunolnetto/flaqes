"""Tests for introspection base classes."""

import pytest

from flaqes.core.schema_graph import SchemaGraph
from flaqes.introspection.base import (
    IntrospectionConfig,
    IntrospectionError,
    IntrospectionResult,
)


class TestIntrospectionConfig:
    """Tests for IntrospectionConfig."""

    def test_default_config(self) -> None:
        config = IntrospectionConfig()

        assert config.schemas == ("public",)
        assert config.include_tables is None
        assert config.exclude_tables == ()
        assert config.include_views is False
        assert config.include_materialized_views is False
        assert config.include_partitions is True
        assert config.include_row_estimates is True
        assert config.include_comments is True
        assert config.include_indexes is True

    def test_custom_schemas(self) -> None:
        config = IntrospectionConfig(schemas=("public", "staging", "analytics"))
        assert len(config.schemas) == 3
        assert "analytics" in config.schemas

    def test_include_specific_tables(self) -> None:
        config = IntrospectionConfig(
            include_tables=("users", "orders", "public.customers")
        )
        assert "users" in config.include_tables  # type: ignore
        assert "public.customers" in config.include_tables  # type: ignore

    def test_exclude_patterns(self) -> None:
        config = IntrospectionConfig(exclude_tables=("pg_*", "temp_*", "*.backup"))
        assert "pg_*" in config.exclude_tables


class TestIntrospectionResult:
    """Tests for IntrospectionResult."""

    def test_basic_result(self) -> None:
        graph = SchemaGraph()
        result = IntrospectionResult(
            graph=graph,
            engine="postgresql",
            engine_version="16.1",
            introspected_schemas=("public",),
            table_count=10,
            relationship_count=5,
        )

        assert result.engine == "postgresql"
        assert result.engine_version == "16.1"
        assert result.table_count == 10
        assert result.relationship_count == 5

    def test_summary(self) -> None:
        result = IntrospectionResult(
            graph=SchemaGraph(),
            engine="postgresql",
            engine_version="16.1",
            table_count=25,
            relationship_count=12,
        )

        summary = result.summary
        assert "postgresql" in summary
        assert "16.1" in summary
        assert "25 tables" in summary
        assert "12 relationships" in summary

    def test_summary_with_unknown_version(self) -> None:
        result = IntrospectionResult(
            graph=SchemaGraph(),
            engine="postgresql",
            table_count=5,
            relationship_count=2,
        )

        summary = result.summary
        assert "unknown version" in summary

    def test_warnings_are_captured(self) -> None:
        result = IntrospectionResult(
            graph=SchemaGraph(),
            engine="postgresql",
            warnings=("Some table skipped", "Another warning"),
        )

        assert len(result.warnings) == 2


class TestIntrospectionError:
    """Tests for IntrospectionError."""

    def test_error_with_cause(self) -> None:
        cause = ValueError("Connection failed")
        error = IntrospectionError(
            "Failed to introspect",
            engine="postgresql",
            cause=cause,
        )

        assert "Failed to introspect" in str(error)
        assert error.engine == "postgresql"
        assert error.cause is cause

    def test_error_without_cause(self) -> None:
        error = IntrospectionError(
            "Unknown error",
            engine="mysql",
        )

        assert error.cause is None


# =============================================================================
# Introspector Base Class Tests
# =============================================================================


from flaqes.core.schema_graph import Column, DataType, PrimaryKey, Table
from flaqes.core.types import DataTypeCategory
from flaqes.introspection.base import Introspector


class MockIntrospector(Introspector):
    """Mock implementation of Introspector for testing."""

    def __init__(self, dsn: str) -> None:
        super().__init__(dsn)
        self._mock_tables: list[Table] = []
        self._connect_called = False
        self._close_called = False

    @property
    def engine(self) -> str:
        return "mock"

    async def _connect(self) -> None:
        self._connect_called = True
        self._connected = True

    async def _get_engine_version(self) -> str | None:
        return "1.0.0-mock"

    async def _introspect_tables(
        self,
        config: IntrospectionConfig,
    ) -> list[Table]:
        # Return pre-configured mock tables
        return self._mock_tables

    async def _introspect_constraints(
        self,
        tables: list[Table],
        config: IntrospectionConfig,
    ) -> None:
        # Nothing to do in mock
        pass

    async def _introspect_indexes(
        self,
        tables: list[Table],
        config: IntrospectionConfig,
    ) -> None:
        # Nothing to do in mock
        pass

    async def close(self) -> None:
        self._close_called = True
        self._connected = False

    def set_mock_tables(self, tables: list[Table]) -> None:
        """Set mock tables to return from introspection."""
        self._mock_tables = tables


class TestIntrospectorBaseClass:
    """Tests for Introspector abstract base class."""

    @pytest.mark.asyncio
    async def test_introspect_with_default_config(self) -> None:
        """Introspect should work with default config."""
        introspector = MockIntrospector("mock://localhost/test")

        # Add a mock table
        table = Table(
            name="users",
            schema="public",
            columns=[
                Column(
                    name="id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                    is_identity=True,
                ),
            ],
            primary_key=PrimaryKey(name="pk", columns=("id",)),
        )
        introspector.set_mock_tables([table])

        result = await introspector.introspect()

        assert result.engine == "mock"
        assert result.engine_version == "1.0.0-mock"
        assert result.table_count == 1
        assert introspector._connect_called

    @pytest.mark.asyncio
    async def test_introspect_with_custom_config(self) -> None:
        """Introspect should accept custom config."""
        introspector = MockIntrospector("mock://localhost/test")
        config = IntrospectionConfig(
            schemas=("public", "staging"),
            include_indexes=False,
        )

        result = await introspector.introspect(config)

        assert result.introspected_schemas == ("public", "staging")

    @pytest.mark.asyncio
    async def test_introspect_table_single(self) -> None:
        """Introspect_table should return a single table."""
        introspector = MockIntrospector("mock://localhost/test")

        table = Table(
            name="orders",
            schema="public",
            columns=[
                Column(
                    name="id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
            ],
            primary_key=PrimaryKey(name="pk", columns=("id",)),
        )
        introspector.set_mock_tables([table])

        result = await introspector.introspect_table("orders")

        assert result is not None
        assert result.name == "orders"

    @pytest.mark.asyncio
    async def test_introspect_table_with_schema(self) -> None:
        """Introspect_table should use provided schema."""
        introspector = MockIntrospector("mock://localhost/test")

        table = Table(
            name="events",
            schema="analytics",
            columns=[
                Column(
                    name="id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
            ],
        )
        introspector.set_mock_tables([table])

        result = await introspector.introspect_table("events", schema="analytics")

        assert result is not None
        assert result.schema == "analytics"

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        """Introspector should work as async context manager."""
        introspector = MockIntrospector("mock://localhost/test")

        async with introspector as ctx:
            assert ctx is introspector
            assert introspector._connect_called
            assert introspector._connected

        assert introspector._close_called
        assert not introspector._connected

    @pytest.mark.asyncio
    async def test_introspect_skips_indexes_when_disabled(self) -> None:
        """Introspect should skip indexes when config says so."""
        introspector = MockIntrospector("mock://localhost/test")
        config = IntrospectionConfig(include_indexes=False)

        # This should complete without calling _introspect_indexes
        result = await introspector.introspect(config)
        assert result.table_count == 0
