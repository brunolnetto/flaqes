"""Tests for tension analyzer module."""

import pytest

from flakes.analysis.tension_analyzer import (
    Alternative,
    DesignTension,
    Effort,
    TensionAnalyzer,
    TensionSignal,
    _detect_wide_table,
    _detect_missing_indexes,
    _detect_nullable_foreign_key,
    _detect_jsonb_overuse,
    _detect_missing_audit_columns,
    _detect_no_primary_key,
    _detect_text_without_constraint,
    _detect_denormalization,
)
from flakes.core.intent import Intent
from flakes.core.schema_graph import (
    Column,
    DataType,
    ForeignKey,
    Index,
    PrimaryKey,
    SchemaGraph,
    Table,
)
from flakes.core.types import DataTypeCategory, Severity, TensionCategory


# =============================================================================
# Helper Functions
# =============================================================================


def make_column(
    name: str,
    category: DataTypeCategory = DataTypeCategory.TEXT,
    nullable: bool = True,
    raw: str | None = None,
) -> Column:
    """Create a column with sensible defaults."""
    return Column(
        name=name,
        data_type=DataType(raw=raw or category.name.lower(), category=category),
        nullable=nullable,
    )


def make_table(
    name: str,
    columns: list[Column],
    primary_key: PrimaryKey | None = None,
    foreign_keys: list[ForeignKey] | None = None,
    indexes: list[Index] | None = None,
    schema: str = "public",
) -> Table:
    """Create a table with sensible defaults."""
    return Table(
        name=name,
        schema=schema,
        columns=columns,
        primary_key=primary_key,
        foreign_keys=foreign_keys or [],
        indexes=indexes or [],
    )


# =============================================================================
# Wide Table Detection Tests
# =============================================================================


class TestWideTableDetection:
    """Tests for wide table tension detection."""

    def test_normal_table_no_tension(self) -> None:
        """Table with few columns should not trigger tension."""
        table = make_table(
            "users",
            columns=[make_column(f"col{i}") for i in range(10)],
        )
        
        result = _detect_wide_table(table, None)
        
        assert result is None

    def test_wide_table_warning(self) -> None:
        """Table with 30+ columns should trigger warning."""
        table = make_table(
            "orders",
            columns=[make_column(f"col{i}") for i in range(35)],
        )
        
        result = _detect_wide_table(table, None)
        
        assert result is not None
        assert result.severity == Severity.WARNING
        assert result.category == TensionCategory.PERFORMANCE

    def test_very_wide_table_critical(self) -> None:
        """Table with 60+ columns should trigger critical."""
        table = make_table(
            "mega_table",
            columns=[make_column(f"col{i}") for i in range(65)],
        )
        
        result = _detect_wide_table(table, None)
        
        assert result is not None
        assert result.severity == Severity.CRITICAL

    def test_olap_higher_threshold(self) -> None:
        """OLAP workload should tolerate wider tables."""
        table = make_table(
            "analytics",
            columns=[make_column(f"col{i}") for i in range(45)],
        )
        
        intent = Intent(
            workload="OLAP",
            write_frequency="low",
            read_patterns=["aggregation"],
            consistency="eventual",
            evolution_rate="low",
            data_volume="large",
            engine="postgresql",
        )
        
        result = _detect_wide_table(table, intent)
        
        # 45 columns should be OK for OLAP (threshold is 50)
        assert result is None


# =============================================================================
# Missing Index Detection Tests
# =============================================================================


class TestMissingIndexDetection:
    """Tests for missing FK index detection."""

    def test_fk_with_index_no_tension(self) -> None:
        """FK column with index should not trigger tension."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("customer_id", DataTypeCategory.INTEGER),
            ],
            foreign_keys=[
                ForeignKey(
                    name="fk_customer",
                    columns=("customer_id",),
                    target_schema="public",
                    target_table="customers",
                    target_columns=("id",),
                ),
            ],
            indexes=[
                Index(
                    name="idx_customer",
                    table_schema="public",
                    table_name="orders",
                    columns=("customer_id",),
                    is_unique=False,
                ),
            ],
        )
        
        result = _detect_missing_indexes(table, [], None)
        
        assert len(result) == 0

    def test_fk_without_index_warning(self) -> None:
        """FK column without index should trigger warning."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("customer_id", DataTypeCategory.INTEGER),
            ],
            foreign_keys=[
                ForeignKey(
                    name="fk_customer",
                    columns=("customer_id",),
                    target_schema="public",
                    target_table="customers",
                    target_columns=("id",),
                ),
            ],
        )
        
        result = _detect_missing_indexes(table, [], None)
        
        assert len(result) == 1
        assert result[0].severity == Severity.WARNING
        assert "customer_id" in result[0].columns

    def test_oltp_critical_severity(self) -> None:
        """OLTP workload should make missing index critical."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("customer_id", DataTypeCategory.INTEGER),
            ],
            foreign_keys=[
                ForeignKey(
                    name="fk_customer",
                    columns=("customer_id",),
                    target_schema="public",
                    target_table="customers",
                    target_columns=("id",),
                ),
            ],
        )
        
        intent = Intent(
            workload="OLTP",
            write_frequency="high",
            read_patterns=["point_lookup"],
            consistency="strong",
            evolution_rate="medium",
            data_volume="medium",
            engine="postgresql",
        )
        
        result = _detect_missing_indexes(table, [], intent)
        
        assert len(result) == 1
        assert result[0].severity == Severity.CRITICAL


# =============================================================================
# Nullable FK Detection Tests
# =============================================================================


class TestNullableFKDetection:
    """Tests for nullable foreign key detection."""

    def test_nullable_fk_detected(self) -> None:
        """Nullable FK should trigger info tension."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("assigned_to", DataTypeCategory.INTEGER, nullable=True),
            ],
            foreign_keys=[
                ForeignKey(
                    name="fk_assigned",
                    columns=("assigned_to",),
                    target_schema="public",
                    target_table="users",
                    target_columns=("id",),
                ),
            ],
        )
        
        result = _detect_nullable_foreign_key(table, None)
        
        assert len(result) == 1
        assert result[0].severity == Severity.INFO
        assert result[0].category == TensionCategory.CONSISTENCY

    def test_non_nullable_fk_no_tension(self) -> None:
        """Non-nullable FK should not trigger tension."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("customer_id", DataTypeCategory.INTEGER, nullable=False),
            ],
            foreign_keys=[
                ForeignKey(
                    name="fk_customer",
                    columns=("customer_id",),
                    target_schema="public",
                    target_table="customers",
                    target_columns=("id",),
                ),
            ],
        )
        
        result = _detect_nullable_foreign_key(table, None)
        
        assert len(result) == 0


# =============================================================================
# JSONB Overuse Detection Tests
# =============================================================================


class TestJSONBOveruseDetection:
    """Tests for JSONB overuse detection."""

    def test_no_json_no_tension(self) -> None:
        """Table without JSON columns should not trigger tension."""
        table = make_table(
            "users",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
            ],
        )
        
        result = _detect_jsonb_overuse(table, None)
        
        assert result is None

    def test_single_json_no_tension(self) -> None:
        """Single JSON column should not trigger tension."""
        table = make_table(
            "users",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
                make_column("email", DataTypeCategory.TEXT),
                make_column("metadata", DataTypeCategory.JSON),
            ],
        )
        
        result = _detect_jsonb_overuse(table, None)
        
        # 1/4 = 25%, below 30% threshold
        assert result is None

    def test_multiple_json_warning(self) -> None:
        """Multiple JSON columns should trigger warning."""
        table = make_table(
            "flexible_data",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("data1", DataTypeCategory.JSON),
                make_column("data2", DataTypeCategory.JSON),
            ],
        )
        
        result = _detect_jsonb_overuse(table, None)
        
        # 2/3 = 67%, above 50% threshold
        assert result is not None
        assert result.severity == Severity.CRITICAL


# =============================================================================
# Missing Audit Columns Detection Tests
# =============================================================================


class TestMissingAuditColumnsDetection:
    """Tests for missing audit columns detection."""

    def test_has_both_audit_columns(self) -> None:
        """Table with both audit columns should not trigger tension."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("created_at", DataTypeCategory.TIMESTAMP),
                make_column("updated_at", DataTypeCategory.TIMESTAMP),
            ],
        )
        
        result = _detect_missing_audit_columns(table, None)
        
        assert result is None

    def test_missing_created_at(self) -> None:
        """Table missing created_at should trigger tension."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("updated_at", DataTypeCategory.TIMESTAMP),
            ],
        )
        
        result = _detect_missing_audit_columns(table, None)
        
        assert result is not None
        assert "created_at" in result.description

    def test_missing_updated_at(self) -> None:
        """Table missing updated_at should trigger tension."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("created_at", DataTypeCategory.TIMESTAMP),
            ],
        )
        
        result = _detect_missing_audit_columns(table, None)
        
        assert result is not None
        assert "updated_at" in result.description


# =============================================================================
# No Primary Key Detection Tests
# =============================================================================


class TestNoPrimaryKeyDetection:
    """Tests for missing primary key detection."""

    def test_has_primary_key(self) -> None:
        """Table with PK should not trigger tension."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
            ],
            primary_key=PrimaryKey(name=None, columns=("id",)),
        )
        
        result = _detect_no_primary_key(table, None)
        
        assert result is None

    def test_missing_primary_key(self) -> None:
        """Table without PK should trigger critical tension."""
        table = make_table(
            "logs",
            columns=[
                make_column("timestamp", DataTypeCategory.TIMESTAMP),
                make_column("message", DataTypeCategory.TEXT),
            ],
        )
        
        result = _detect_no_primary_key(table, None)
        
        assert result is not None
        assert result.severity == Severity.CRITICAL
        assert result.id == "no_primary_key"


# =============================================================================
# Text Without Constraint Detection Tests
# =============================================================================


class TestTextWithoutConstraintDetection:
    """Tests for unbounded text column detection."""

    def test_unbounded_text_detected(self) -> None:
        """Unbounded TEXT column should trigger tension."""
        table = make_table(
            "posts",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("content", DataTypeCategory.TEXT, raw="text"),
            ],
        )
        
        result = _detect_text_without_constraint(table, None)
        
        assert len(result) == 1
        assert result[0].severity == Severity.INFO

    def test_varchar_with_length_no_tension(self) -> None:
        """VARCHAR with length should not trigger tension."""
        table = make_table(
            "users",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT, raw="varchar(255)"),
            ],
        )
        
        result = _detect_text_without_constraint(table, None)
        
        # varchar(255) has explicit length, should not trigger
        assert len(result) == 0


# =============================================================================
# Denormalization Detection Tests
# =============================================================================


class TestDenormalizationDetection:
    """Tests for denormalization pattern detection."""

    def test_multiple_name_columns_detected(self) -> None:
        """Multiple *_name columns should trigger tension."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("customer_name", DataTypeCategory.TEXT),
                make_column("product_name", DataTypeCategory.TEXT),
                make_column("shipping_name", DataTypeCategory.TEXT),
            ],
        )
        
        graph = SchemaGraph.from_tables([table])
        result = _detect_denormalization(table, graph, None)
        
        assert len(result) == 1
        assert result[0].category == TensionCategory.NORMALIZATION

    def test_single_name_column_no_tension(self) -> None:
        """Single *_name column should not trigger tension."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("customer_name", DataTypeCategory.TEXT),
            ],
        )
        
        graph = SchemaGraph.from_tables([table])
        result = _detect_denormalization(table, graph, None)
        
        assert len(result) == 0


# =============================================================================
# TensionAnalyzer Class Tests
# =============================================================================


class TestTensionAnalyzer:
    """Tests for TensionAnalyzer class."""

    def test_analyze_table_returns_tensions(self) -> None:
        """analyze_table should return list of tensions."""
        table = make_table(
            "problematic",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("data", DataTypeCategory.JSON),
                make_column("more_data", DataTypeCategory.JSON),
                make_column("customer_id", DataTypeCategory.INTEGER),
            ],
            foreign_keys=[
                ForeignKey(
                    name="fk_customer",
                    columns=("customer_id",),
                    target_schema="public",
                    target_table="customers",
                    target_columns=("id",),
                ),
            ],
        )
        
        graph = SchemaGraph.from_tables([table])
        analyzer = TensionAnalyzer()
        
        tensions = analyzer.analyze_table(table, graph)
        
        assert len(tensions) >= 1  # Should detect something

    def test_analyze_returns_dict(self) -> None:
        """analyze should return dict mapping tables to tensions."""
        table1 = make_table(
            "no_pk",
            columns=[make_column("data", DataTypeCategory.TEXT)],
        )
        table2 = make_table(
            "with_pk",
            columns=[make_column("id", DataTypeCategory.INTEGER)],
            primary_key=PrimaryKey(name=None, columns=("id",)),
        )
        
        graph = SchemaGraph.from_tables([table1, table2])
        analyzer = TensionAnalyzer()
        
        results = analyzer.analyze(graph)
        
        assert "public.no_pk" in results
        # Table with PK might have fewer or no tensions

    def test_min_severity_filter(self) -> None:
        """min_severity should filter out lower severity tensions."""
        table = make_table(
            "test",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("content", DataTypeCategory.TEXT, raw="text"),
            ],
        )
        
        graph = SchemaGraph.from_tables([table])
        
        # With INFO threshold, should include text constraint tension
        analyzer_info = TensionAnalyzer(min_severity=Severity.INFO)
        tensions_info = analyzer_info.analyze_table(table, graph)
        
        # With WARNING threshold, should exclude INFO tensions
        analyzer_warn = TensionAnalyzer(min_severity=Severity.WARNING)
        tensions_warn = analyzer_warn.analyze_table(table, graph)
        
        # WARNING filter should have fewer or equal tensions
        assert len(tensions_warn) <= len(tensions_info)

    def test_get_summary(self) -> None:
        """get_summary should return counts by category and severity."""
        table = make_table(
            "test",
            columns=[make_column("data", DataTypeCategory.TEXT, raw="text")],
        )
        
        graph = SchemaGraph.from_tables([table])
        analyzer = TensionAnalyzer()
        
        summary = analyzer.get_summary(graph)
        
        assert "total" in summary
        assert "critical" in summary
        assert "warning" in summary
        assert "info" in summary


# =============================================================================
# Data Structure Tests
# =============================================================================


class TestAlternative:
    """Tests for Alternative dataclass."""

    def test_alternative_creation(self) -> None:
        """Alternative should be creatable."""
        alt = Alternative(
            description="Add an index",
            trade_off="Slower writes",
            effort=Effort.LOW,
            example_ddl="CREATE INDEX ...",
        )
        
        assert alt.description == "Add an index"
        assert alt.effort == Effort.LOW

    def test_alternative_summary(self) -> None:
        """summary should include effort level."""
        alt = Alternative(
            description="Split table",
            trade_off="More JOINs",
            effort=Effort.HIGH,
        )
        
        summary = alt.summary()
        
        assert "high" in summary.lower()


class TestDesignTension:
    """Tests for DesignTension dataclass."""

    def test_is_critical(self) -> None:
        """is_critical should identify critical tensions."""
        tension = DesignTension(
            id="test",
            category=TensionCategory.PERFORMANCE,
            description="Test tension",
            current_benefit="None",
            risk="High",
            breaking_point="Now",
            severity=Severity.CRITICAL,
            table="public.test",
        )
        
        assert tension.is_critical
        assert not tension.is_warning

    def test_is_warning(self) -> None:
        """is_warning should identify warning tensions."""
        tension = DesignTension(
            id="test",
            category=TensionCategory.PERFORMANCE,
            description="Test tension",
            current_benefit="None",
            risk="Medium",
            breaking_point="Later",
            severity=Severity.WARNING,
            table="public.test",
        )
        
        assert not tension.is_critical
        assert tension.is_warning

    def test_summary(self) -> None:
        """summary should include severity and table."""
        tension = DesignTension(
            id="test",
            category=TensionCategory.CONSISTENCY,
            description="Missing index",
            current_benefit="Fast writes",
            risk="Slow reads",
            breaking_point="10K rows",
            severity=Severity.WARNING,
            table="public.orders",
        )
        
        summary = tension.summary()
        
        assert "WARNING" in summary
        assert "public.orders" in summary


class TestTensionSignal:
    """Tests for TensionSignal NamedTuple."""

    def test_signal_creation(self) -> None:
        """Signal should be creatable."""
        signal = TensionSignal(
            name="test",
            description="A test signal",
            severity_weight=0.5,
        )
        
        assert signal.name == "test"
        assert signal.severity_weight == 0.5


class TestEffort:
    """Tests for Effort enum."""

    def test_effort_values(self) -> None:
        """Effort should have correct values."""
        assert Effort.LOW.value == "low"
        assert Effort.MEDIUM.value == "medium"
        assert Effort.HIGH.value == "high"
