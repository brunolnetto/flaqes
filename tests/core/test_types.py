"""Tests for core type definitions."""

import pytest

from flakes.core.types import (
    Cardinality,
    ConstraintType,
    DataTypeCategory,
    Effort,
    IndexMethod,
    RoleType,
    Severity,
    TensionCategory,
)


class TestCardinality:
    """Tests for Cardinality enum."""

    def test_all_cardinalities_defined(self) -> None:
        assert Cardinality.ONE_TO_ONE
        assert Cardinality.ONE_TO_MANY
        assert Cardinality.MANY_TO_ONE
        assert Cardinality.MANY_TO_MANY


class TestConstraintType:
    """Tests for ConstraintType enum."""

    def test_all_constraint_types_defined(self) -> None:
        assert ConstraintType.PRIMARY_KEY
        assert ConstraintType.FOREIGN_KEY
        assert ConstraintType.UNIQUE
        assert ConstraintType.CHECK
        assert ConstraintType.EXCLUSION
        assert ConstraintType.NOT_NULL


class TestIndexMethod:
    """Tests for IndexMethod enum."""

    def test_btree_is_default(self) -> None:
        assert IndexMethod.BTREE.value == "btree"

    def test_all_postgres_methods(self) -> None:
        methods = {m.value for m in IndexMethod}
        assert methods == {"btree", "hash", "gin", "gist", "spgist", "brin"}


class TestDataTypeCategory:
    """Tests for DataTypeCategory enum."""

    def test_numeric_categories(self) -> None:
        assert DataTypeCategory.INTEGER
        assert DataTypeCategory.FLOAT
        assert DataTypeCategory.DECIMAL

    def test_temporal_categories(self) -> None:
        assert DataTypeCategory.TIMESTAMP
        assert DataTypeCategory.DATE
        assert DataTypeCategory.TIME
        assert DataTypeCategory.INTERVAL

    def test_json_category(self) -> None:
        assert DataTypeCategory.JSON


class TestRoleType:
    """Tests for RoleType enum."""

    def test_dimensional_roles(self) -> None:
        assert RoleType.FACT
        assert RoleType.DIMENSION

    def test_temporal_roles(self) -> None:
        assert RoleType.EVENT
        assert RoleType.SNAPSHOT
        assert RoleType.SCD_TYPE_1
        assert RoleType.SCD_TYPE_2

    def test_structural_roles(self) -> None:
        assert RoleType.JUNCTION
        assert RoleType.LOOKUP
        assert RoleType.POLYMORPHIC

    def test_fallback_roles(self) -> None:
        assert RoleType.ENTITY
        assert RoleType.UNKNOWN


class TestSeverity:
    """Tests for Severity enum."""

    def test_severity_ordering_conceptually(self) -> None:
        # We can't compare enums directly, but we can check they exist
        assert Severity.INFO
        assert Severity.WARNING
        assert Severity.CRITICAL


class TestEffort:
    """Tests for Effort enum."""

    def test_all_effort_levels(self) -> None:
        assert Effort.LOW
        assert Effort.MEDIUM
        assert Effort.HIGH


class TestTensionCategory:
    """Tests for TensionCategory enum."""

    def test_all_tension_categories(self) -> None:
        assert TensionCategory.NORMALIZATION
        assert TensionCategory.PERFORMANCE
        assert TensionCategory.EVOLUTION
        assert TensionCategory.CONSISTENCY
        assert TensionCategory.COMPLEXITY
