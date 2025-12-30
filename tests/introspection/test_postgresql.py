"""Tests for PostgreSQL introspector."""

import pytest

# Check if asyncpg is available
try:
    import asyncpg

    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

# Skip all tests in this module if asyncpg is not installed
pytestmark = pytest.mark.skipif(
    not HAS_ASYNCPG,
    reason="asyncpg not installed - install with: pip install flaqes[postgresql]",
)


if HAS_ASYNCPG:
    from flaqes.core.types import DataTypeCategory, IndexMethod
    from flaqes.introspection.postgresql import (
        PostgreSQLIntrospector,
        _categorize_type,
        _map_index_method,
    )


@pytest.mark.skipif(not HAS_ASYNCPG, reason="asyncpg not installed")
class TestTypeCategorization:
    """Tests for PostgreSQL type categorization."""

    def test_integer_types(self) -> None:
        for type_name in ["int2", "int4", "int8", "integer", "bigint", "smallint"]:
            category, is_array, element = _categorize_type(type_name)
            assert category == DataTypeCategory.INTEGER
            assert not is_array
            assert element is None

    def test_float_types(self) -> None:
        for type_name in ["float4", "float8", "real", "double precision"]:
            category, is_array, element = _categorize_type(type_name)
            assert category == DataTypeCategory.FLOAT
            assert not is_array

    def test_decimal_types(self) -> None:
        for type_name in ["numeric", "decimal", "money"]:
            category, is_array, element = _categorize_type(type_name)
            assert category == DataTypeCategory.DECIMAL

    def test_text_types(self) -> None:
        for type_name in ["text", "varchar", "character varying", "char"]:
            category, is_array, element = _categorize_type(type_name)
            assert category == DataTypeCategory.TEXT

    def test_boolean_types(self) -> None:
        for type_name in ["bool", "boolean"]:
            category, is_array, element = _categorize_type(type_name)
            assert category == DataTypeCategory.BOOLEAN

    def test_timestamp_types(self) -> None:
        for type_name in ["timestamp", "timestamptz", "timestamp with time zone"]:
            category, is_array, element = _categorize_type(type_name)
            assert category == DataTypeCategory.TIMESTAMP

    def test_json_types(self) -> None:
        for type_name in ["json", "jsonb"]:
            category, is_array, element = _categorize_type(type_name)
            assert category == DataTypeCategory.JSON

    def test_uuid_type(self) -> None:
        category, is_array, element = _categorize_type("uuid")
        assert category == DataTypeCategory.UUID

    def test_array_type_with_brackets(self) -> None:
        category, is_array, element = _categorize_type("integer[]")
        assert category == DataTypeCategory.ARRAY
        assert is_array
        assert element == "integer"

    def test_array_type_with_underscore_prefix(self) -> None:
        category, is_array, element = _categorize_type("_int4")
        assert category == DataTypeCategory.ARRAY
        assert is_array
        assert element == "int4"

    def test_unknown_type(self) -> None:
        category, is_array, element = _categorize_type("custom_type")
        assert category == DataTypeCategory.OTHER
        assert not is_array


@pytest.mark.skipif(not HAS_ASYNCPG, reason="asyncpg not installed")
class TestIndexMethodMapping:
    """Tests for index method mapping."""

    def test_btree(self) -> None:
        assert _map_index_method("btree") == IndexMethod.BTREE

    def test_gin(self) -> None:
        assert _map_index_method("gin") == IndexMethod.GIN

    def test_gist(self) -> None:
        assert _map_index_method("gist") == IndexMethod.GIST

    def test_hash(self) -> None:
        assert _map_index_method("hash") == IndexMethod.HASH

    def test_brin(self) -> None:
        assert _map_index_method("brin") == IndexMethod.BRIN

    def test_unknown_defaults_to_btree(self) -> None:
        assert _map_index_method("unknown") == IndexMethod.BTREE

    def test_case_insensitive(self) -> None:
        assert _map_index_method("BTREE") == IndexMethod.BTREE
        assert _map_index_method("GIN") == IndexMethod.GIN


@pytest.mark.skipif(not HAS_ASYNCPG, reason="asyncpg not installed")
class TestPostgreSQLIntrospector:
    """Tests for PostgreSQLIntrospector class."""

    def test_engine_property(self) -> None:
        introspector = PostgreSQLIntrospector("postgresql://localhost/test")
        assert introspector.engine == "postgresql"

    def test_not_connected_initially(self) -> None:
        introspector = PostgreSQLIntrospector("postgresql://localhost/test")
        assert not introspector._connected

    def test_dsn_stored(self) -> None:
        dsn = "postgresql://user:pass@localhost:5432/mydb"
        introspector = PostgreSQLIntrospector(dsn)
        assert introspector._dsn == dsn


# Integration tests would go here, but require a real PostgreSQL instance
# They should be marked with @pytest.mark.integration and use testcontainers
