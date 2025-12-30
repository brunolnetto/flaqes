"""Tests for introspection registry."""

import pytest

from flaqes.introspection.registry import (
    _ensure_engine_loaded,
    get_introspector,
    get_introspector_from_dsn,
    is_engine_supported,
    list_supported_engines,
)

# Check if asyncpg is available
try:
    import asyncpg

    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False


class TestRegistry:
    """Tests for introspector registry."""

    @pytest.mark.skipif(not HAS_ASYNCPG, reason="asyncpg not installed")
    def test_postgresql_is_registered_when_asyncpg_available(self) -> None:
        """PostgreSQL introspector should be registered when asyncpg is available."""
        _ensure_engine_loaded("postgresql")
        assert is_engine_supported("postgresql")

    def test_list_supported_engines_is_sorted(self) -> None:
        engines = list_supported_engines()
        # List should be sorted
        assert engines == sorted(engines)

    @pytest.mark.skipif(not HAS_ASYNCPG, reason="asyncpg not installed")
    def test_get_introspector_postgresql(self) -> None:
        introspector = get_introspector("postgresql", "postgresql://localhost/test")
        assert introspector.engine == "postgresql"

    @pytest.mark.skipif(HAS_ASYNCPG, reason="asyncpg is installed")
    def test_get_introspector_postgresql_without_asyncpg(self) -> None:
        """Should raise ImportError with helpful message when asyncpg not installed."""
        with pytest.raises(ImportError) as exc_info:
            get_introspector("postgresql", "postgresql://localhost/test")

        assert "asyncpg" in str(exc_info.value)
        assert "flaqes[postgresql]" in str(exc_info.value)

    def test_get_introspector_mysql_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError) as exc_info:
            get_introspector("mysql", "mysql://localhost/test")

        assert "MySQL" in str(exc_info.value)
        assert "not yet implemented" in str(exc_info.value)

    def test_get_introspector_sqlite_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError) as exc_info:
            get_introspector("sqlite", "sqlite:///test.db")

        assert "SQLite" in str(exc_info.value)

    def test_get_introspector_unsupported(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            get_introspector("oracle", "oracle://localhost/test")

        assert "Unsupported database engine" in str(exc_info.value)
        assert "oracle" in str(exc_info.value)


class TestDSNInference:
    """Tests for DSN-based engine inference."""

    @pytest.mark.skipif(not HAS_ASYNCPG, reason="asyncpg not installed")
    def test_postgresql_dsn(self) -> None:
        introspector = get_introspector_from_dsn("postgresql://localhost/mydb")
        assert introspector.engine == "postgresql"

    @pytest.mark.skipif(not HAS_ASYNCPG, reason="asyncpg not installed")
    def test_postgres_dsn(self) -> None:
        introspector = get_introspector_from_dsn("postgres://localhost/mydb")
        assert introspector.engine == "postgresql"

    def test_mysql_dsn_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError) as exc_info:
            get_introspector_from_dsn("mysql://localhost/mydb")

        assert "MySQL" in str(exc_info.value)

    def test_sqlite_dsn_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError) as exc_info:
            get_introspector_from_dsn("sqlite:///mydb.db")

        assert "SQLite" in str(exc_info.value)

    def test_unknown_dsn_format(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            get_introspector_from_dsn("unknown://localhost/mydb")

        assert "Cannot infer database engine" in str(exc_info.value)
