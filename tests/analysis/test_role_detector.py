"""Tests for table role detection."""

import pytest

from flaqes.analysis.role_detector import (
    RoleDetector,
    Signal,
    SignalType,
    TableRoleResult,
    _detect_dimension_signals,
    _detect_event_signals,
    _detect_fact_signals,
    _detect_junction_signals,
    _detect_lookup_signals,
    _detect_scd_type2_signals,
)
from flaqes.core.schema_graph import (
    Column,
    DataType,
    ForeignKey,
    PrimaryKey,
    SchemaGraph,
    Table,
)
from flaqes.core.types import DataTypeCategory, RoleType

# =============================================================================
# Fixtures - Table Builders
# =============================================================================


def make_column(
    name: str,
    category: DataTypeCategory = DataTypeCategory.TEXT,
    nullable: bool = True,
    is_identity: bool = False,
) -> Column:
    """Helper to create a column quickly."""
    type_map = {
        DataTypeCategory.INTEGER: "integer",
        DataTypeCategory.TEXT: "text",
        DataTypeCategory.TIMESTAMP: "timestamp",
        DataTypeCategory.JSON: "jsonb",
        DataTypeCategory.BOOLEAN: "boolean",
        DataTypeCategory.DECIMAL: "numeric",
        DataTypeCategory.FLOAT: "double precision",
        DataTypeCategory.UUID: "uuid",
    }
    raw_type = type_map.get(category, "text")
    return Column(
        name=name,
        data_type=DataType(raw=raw_type, category=category),
        nullable=nullable,
        is_identity=is_identity,
    )


def make_table(
    name: str,
    columns: list[Column] | None = None,
    pk_columns: tuple[str, ...] | None = None,
    fk_targets: list[tuple[str, str]] | None = None,
    schema: str = "public",
    row_estimate: int | None = None,
) -> Table:
    """
    Helper to create a table quickly.

    Args:
        name: Table name
        columns: List of columns. If None, creates just an 'id' column.
        pk_columns: Primary key column names. If None and columns has 'id', uses that.
        fk_targets: List of (column_name, target_table) tuples.
        schema: Schema name.
        row_estimate: Estimated row count.
    """
    if columns is None:
        columns = [make_column("id", DataTypeCategory.INTEGER, False, True)]

    pk = None
    if pk_columns:
        pk = PrimaryKey(name=f"{name}_pkey", columns=pk_columns)
    elif any(c.name == "id" for c in columns):
        pk = PrimaryKey(name=f"{name}_pkey", columns=("id",))

    fks = []
    if fk_targets:
        for col_name, target_table in fk_targets:
            fks.append(
                ForeignKey(
                    name=f"{name}_{col_name}_fkey",
                    columns=(col_name,),
                    target_schema="public",
                    target_table=target_table,
                    target_columns=("id",),
                )
            )

    return Table(
        name=name,
        schema=schema,
        columns=columns,
        primary_key=pk,
        foreign_keys=fks,
        row_estimate=row_estimate,
    )


@pytest.fixture
def empty_graph() -> SchemaGraph:
    """Create an empty schema graph."""
    return SchemaGraph()


# =============================================================================
# Signal Tests
# =============================================================================


class TestSignal:
    """Tests for Signal dataclass."""

    def test_signal_creation(self) -> None:
        signal = Signal(
            name="test_signal",
            description="A test signal",
            signal_type=SignalType.STRUCTURAL,
            weight=0.8,
        )
        assert signal.name == "test_signal"
        assert signal.weight == 0.8

    def test_signal_str(self) -> None:
        signal = Signal(
            name="my_signal",
            description="Description here",
            signal_type=SignalType.NAMING,
        )
        assert "my_signal" in str(signal)
        assert "Description here" in str(signal)


class TestTableRoleResult:
    """Tests for TableRoleResult."""

    def test_is_confident_high(self) -> None:
        result = TableRoleResult(
            table="public.test",
            primary_role=RoleType.FACT,
            confidence=0.85,
        )
        assert result.is_confident

    def test_is_confident_low(self) -> None:
        result = TableRoleResult(
            table="public.test",
            primary_role=RoleType.FACT,
            confidence=0.5,
        )
        assert not result.is_confident

    def test_is_ambiguous_close_alternatives(self) -> None:
        result = TableRoleResult(
            table="public.test",
            primary_role=RoleType.FACT,
            confidence=0.6,
            alternatives=[(RoleType.EVENT, 0.55)],
        )
        assert result.is_ambiguous

    def test_is_not_ambiguous_clear_winner(self) -> None:
        result = TableRoleResult(
            table="public.test",
            primary_role=RoleType.FACT,
            confidence=0.8,
            alternatives=[(RoleType.EVENT, 0.3)],
        )
        assert not result.is_ambiguous

    def test_summary(self) -> None:
        result = TableRoleResult(
            table="public.orders",
            primary_role=RoleType.FACT,
            confidence=0.85,
        )
        summary = result.summary()
        assert "public.orders" in summary
        assert "FACT" in summary
        assert "85%" in summary


# =============================================================================
# Junction Table Detection
# =============================================================================


class TestJunctionDetection:
    """Tests for junction table detection."""

    def test_classic_many_to_many_junction(self) -> None:
        """A classic junction table with composite PK of two FKs."""
        table = make_table(
            "user_roles",
            columns=[
                make_column("user_id", DataTypeCategory.INTEGER, False),
                make_column("role_id", DataTypeCategory.INTEGER, False),
            ],
            pk_columns=("user_id", "role_id"),
            fk_targets=[("user_id", "users"), ("role_id", "roles")],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_junction_signals(table, graph)

        signal_names = {s.name for s in signals}
        assert "pk_is_fk_composite" in signal_names
        assert "exactly_two_fks" in signal_names

    def test_junction_with_extra_columns(self) -> None:
        """Junction with additional metadata columns."""
        table = make_table(
            "order_products",
            columns=[
                make_column("order_id", DataTypeCategory.INTEGER, False),
                make_column("product_id", DataTypeCategory.INTEGER, False),
                make_column("quantity", DataTypeCategory.INTEGER, False),
                make_column("created_at", DataTypeCategory.TIMESTAMP),
            ],
            pk_columns=("order_id", "product_id"),
            fk_targets=[("order_id", "orders"), ("product_id", "products")],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_junction_signals(table, graph)

        signal_names = {s.name for s in signals}
        assert "exactly_two_fks" in signal_names
        # Still minimal payload (quantity is the only meaningful extra column)
        assert "minimal_payload" in signal_names

    def test_not_a_junction(self) -> None:
        """Regular table should not trigger junction signals."""
        table = make_table(
            "users",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("name", DataTypeCategory.TEXT),
                make_column("email", DataTypeCategory.TEXT),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_junction_signals(table, graph)
        assert len(signals) == 0


# =============================================================================
# Fact Table Detection
# =============================================================================


class TestFactDetection:
    """Tests for fact table detection."""

    def test_classic_fact_table(self) -> None:
        """Fact table with multiple FKs and measures."""
        table = make_table(
            "sales_facts",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("customer_id", DataTypeCategory.INTEGER, False),
                make_column("product_id", DataTypeCategory.INTEGER, False),
                make_column("store_id", DataTypeCategory.INTEGER, False),
                make_column("date_id", DataTypeCategory.INTEGER, False),
                make_column("quantity", DataTypeCategory.INTEGER, False),
                make_column("amount", DataTypeCategory.DECIMAL, False),
                make_column("discount", DataTypeCategory.DECIMAL),
                make_column("created_at", DataTypeCategory.TIMESTAMP),
            ],
            fk_targets=[
                ("customer_id", "customers"),
                ("product_id", "products"),
                ("store_id", "stores"),
                ("date_id", "dates"),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_fact_signals(table, graph)

        signal_names = {s.name for s in signals}
        assert "many_fks" in signal_names
        assert "numeric_measures" in signal_names
        assert "fact_table_name" in signal_names  # 'facts' in name

    def test_orders_table_as_fact(self) -> None:
        """Orders is a common fact table pattern."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("customer_id", DataTypeCategory.INTEGER),
                make_column("product_id", DataTypeCategory.INTEGER),
                make_column("status_id", DataTypeCategory.INTEGER),
                make_column("total_amount", DataTypeCategory.DECIMAL),
                make_column("tax", DataTypeCategory.DECIMAL),
                make_column("created_at", DataTypeCategory.TIMESTAMP),
            ],
            fk_targets=[
                ("customer_id", "customers"),
                ("product_id", "products"),
                ("status_id", "statuses"),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_fact_signals(table, graph)

        signal_names = {s.name for s in signals}
        assert "many_fks" in signal_names
        assert "numeric_measures" in signal_names
        assert "fact_table_name" in signal_names  # 'orders' in name


# =============================================================================
# Dimension Table Detection
# =============================================================================


class TestDimensionDetection:
    """Tests for dimension table detection."""

    def test_classic_dimension(self) -> None:
        """Dimension table referenced by facts."""
        customers = make_table(
            "customers",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("name", DataTypeCategory.TEXT),
                make_column("email", DataTypeCategory.TEXT),
                make_column("address", DataTypeCategory.TEXT),
                make_column("city", DataTypeCategory.TEXT),
            ],
        )
        orders = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("customer_id", DataTypeCategory.INTEGER),
            ],
            fk_targets=[("customer_id", "customers")],
        )
        facts = make_table(
            "sales_facts",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("customer_id", DataTypeCategory.INTEGER),
            ],
            fk_targets=[("customer_id", "customers")],
        )

        graph = SchemaGraph.from_tables([customers, orders, facts])

        signals = _detect_dimension_signals(customers, graph)

        signal_names = {s.name for s in signals}
        assert "heavily_referenced" in signal_names  # Referenced by 2 tables
        assert "no_outgoing_fks" in signal_names
        assert "text_heavy" in signal_names
        assert "dimension_table_name" in signal_names  # 'customer' in name

    def test_dim_prefix_naming(self) -> None:
        """Tables with dim_ prefix should be detected."""
        table = make_table(
            "dim_product",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("sku", DataTypeCategory.TEXT),
                make_column("name", DataTypeCategory.TEXT),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_dimension_signals(table, graph)

        signal_names = {s.name for s in signals}
        assert "dimension_table_name" in signal_names


# =============================================================================
# Event/Log Table Detection
# =============================================================================


class TestEventDetection:
    """Tests for event/log table detection."""

    def test_event_log_table(self) -> None:
        """Classic event log with append-only pattern."""
        table = make_table(
            "user_events",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("user_id", DataTypeCategory.INTEGER),
                make_column("event_type", DataTypeCategory.TEXT),
                make_column("payload", DataTypeCategory.JSON),
                make_column("created_at", DataTypeCategory.TIMESTAMP),
            ],
            fk_targets=[("user_id", "users")],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_event_signals(table, graph)

        signal_names = {s.name for s in signals}
        assert "append_only_timestamps" in signal_names
        assert "event_table_name" in signal_names
        assert "event_type_column" in signal_names
        assert "json_payload" in signal_names

    def test_audit_log(self) -> None:
        """Audit log table."""
        table = make_table(
            "audit_log",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("action", DataTypeCategory.TEXT),
                make_column("user_id", DataTypeCategory.INTEGER),
                make_column("timestamp", DataTypeCategory.TIMESTAMP),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_event_signals(table, graph)

        signal_names = {s.name for s in signals}
        assert "event_table_name" in signal_names  # 'audit' and 'log' in name
        assert "event_type_column" in signal_names  # 'action' column


# =============================================================================
# SCD Type 2 Detection
# =============================================================================


class TestSCDType2Detection:
    """Tests for SCD Type 2 detection."""

    def test_classic_scd2(self) -> None:
        """SCD Type 2 with valid_from, valid_to, is_current."""
        table = make_table(
            "customer_history",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("customer_id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
                make_column("address", DataTypeCategory.TEXT),
                make_column("valid_from", DataTypeCategory.TIMESTAMP),
                make_column("valid_to", DataTypeCategory.TIMESTAMP),
                make_column("is_current", DataTypeCategory.BOOLEAN),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_scd_type2_signals(table, graph)

        signal_names = {s.name for s in signals}
        assert "validity_period" in signal_names
        assert "is_current_flag" in signal_names

    def test_effective_dates(self) -> None:
        """Alternative naming: effective_from/to."""
        table = make_table(
            "price_history",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("product_id", DataTypeCategory.INTEGER),
                make_column("price", DataTypeCategory.DECIMAL),
                make_column("effective_from", DataTypeCategory.TIMESTAMP),
                make_column("effective_to", DataTypeCategory.TIMESTAMP),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_scd_type2_signals(table, graph)

        signal_names = {s.name for s in signals}
        assert "validity_period" in signal_names


# =============================================================================
# Lookup Table Detection
# =============================================================================


class TestLookupDetection:
    """Tests for lookup/reference table detection."""

    def test_status_lookup(self) -> None:
        """Simple status lookup table."""
        table = make_table(
            "order_status",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("code", DataTypeCategory.TEXT),
                make_column("name", DataTypeCategory.TEXT),
            ],
            row_estimate=10,
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_lookup_signals(table, graph)

        signal_names = {s.name for s in signals}
        assert "narrow_table" in signal_names
        assert "lookup_table_name" in signal_names  # 'status' in name
        assert "code_description_pattern" in signal_names
        assert "no_dependencies" in signal_names
        assert "low_cardinality" in signal_names

    def test_category_lookup(self) -> None:
        """Category lookup table."""
        table = make_table(
            "product_categories",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("name", DataTypeCategory.TEXT),
                make_column("description", DataTypeCategory.TEXT),
            ],
            row_estimate=50,
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_lookup_signals(table, graph)

        signal_names = {s.name for s in signals}
        assert "narrow_table" in signal_names
        assert "lookup_table_name" in signal_names  # 'categories' in name


# =============================================================================
# Full Role Detector Tests
# =============================================================================


class TestRoleDetector:
    """Tests for RoleDetector class."""

    def test_detect_junction_role(self) -> None:
        """Detector should identify junction tables."""
        table = make_table(
            "user_roles",
            columns=[
                make_column("user_id", DataTypeCategory.INTEGER, False),
                make_column("role_id", DataTypeCategory.INTEGER, False),
            ],
            pk_columns=("user_id", "role_id"),
            fk_targets=[("user_id", "users"), ("role_id", "roles")],
        )
        graph = SchemaGraph.from_tables([table])

        detector = RoleDetector()
        result = detector.detect(table, graph)

        assert result.primary_role == RoleType.JUNCTION
        assert result.confidence > 0.5
        assert len(result.signals) > 0

    def test_detect_fact_role(self) -> None:
        """Detector should identify fact tables."""
        table = make_table(
            "sales_facts",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("customer_id", DataTypeCategory.INTEGER),
                make_column("product_id", DataTypeCategory.INTEGER),
                make_column("store_id", DataTypeCategory.INTEGER),
                make_column("quantity", DataTypeCategory.INTEGER),
                make_column("amount", DataTypeCategory.DECIMAL),
            ],
            fk_targets=[
                ("customer_id", "customers"),
                ("product_id", "products"),
                ("store_id", "stores"),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        detector = RoleDetector()
        result = detector.detect(table, graph)

        assert result.primary_role == RoleType.FACT
        assert result.confidence > 0.5

    def test_detect_scd2_role(self) -> None:
        """Detector should identify SCD Type 2 tables."""
        table = make_table(
            "customer_history",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("customer_id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
                make_column("valid_from", DataTypeCategory.TIMESTAMP),
                make_column("valid_to", DataTypeCategory.TIMESTAMP),
                make_column("is_current", DataTypeCategory.BOOLEAN),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        detector = RoleDetector()
        result = detector.detect(table, graph)

        assert result.primary_role == RoleType.SCD_TYPE_2
        assert result.confidence > 0.7

    def test_detect_unknown_for_ambiguous(self) -> None:
        """Detector should return UNKNOWN for tables with no signals."""
        table = make_table(
            "xyz_abc",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("value", DataTypeCategory.TEXT),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        # Use a detector with no built-in detectors
        detector = RoleDetector(role_detectors=[])
        result = detector.detect(table, graph)

        assert result.primary_role == RoleType.UNKNOWN
        assert result.confidence == 0.0

    def test_detect_all(self) -> None:
        """Detector should analyze all tables in a graph."""
        users = make_table("users")
        roles = make_table("roles")
        user_roles = make_table(
            "user_roles",
            columns=[
                make_column("user_id", DataTypeCategory.INTEGER, False),
                make_column("role_id", DataTypeCategory.INTEGER, False),
            ],
            pk_columns=("user_id", "role_id"),
            fk_targets=[("user_id", "users"), ("role_id", "roles")],
        )
        graph = SchemaGraph.from_tables([users, roles, user_roles])

        detector = RoleDetector()
        results = detector.detect_all(graph)

        assert len(results) == 3
        assert "public.user_roles" in results
        assert results["public.user_roles"].primary_role == RoleType.JUNCTION

    def test_alternatives_included(self) -> None:
        """Should include alternative role hypotheses."""
        # A table that could be either a dimension or a lookup
        table = make_table(
            "product_types",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("code", DataTypeCategory.TEXT),
                make_column("name", DataTypeCategory.TEXT),
                make_column("description", DataTypeCategory.TEXT),
            ],
        )
        orders = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("type_id", DataTypeCategory.INTEGER),
            ],
            fk_targets=[("type_id", "product_types")],
        )
        graph = SchemaGraph.from_tables([table, orders])

        detector = RoleDetector()
        result = detector.detect(table, graph)

        # Could be DIMENSION or LOOKUP
        all_roles = [result.primary_role] + [r for r, _ in result.alternatives]
        assert RoleType.DIMENSION in all_roles or RoleType.LOOKUP in all_roles


# =============================================================================
# Additional Coverage Tests
# =============================================================================


class TestTableRoleResultSummaryWithAlternatives:
    """Tests for summary with ambiguous alternatives."""

    def test_summary_shows_alternatives_when_ambiguous(self) -> None:
        """When ambiguous, summary should show top alternative."""
        result = TableRoleResult(
            table="public.mixed",
            primary_role=RoleType.FACT,
            confidence=0.55,
            alternatives=[(RoleType.EVENT, 0.50)],
        )
        # This is ambiguous (diff < 0.2)
        assert result.is_ambiguous
        summary = result.summary()
        assert "also possibly" in summary
        assert "EVENT" in summary


class TestJunctionPKSubsetOfFKs:
    """Tests for pk_subset_of_fks signal."""

    def test_pk_subset_of_fk_columns(self) -> None:
        """PK is subset of FK columns (not exact match)."""
        # PK is (user_id), but FKs cover (user_id, role_id, extra_id)
        table = Table(
            name="complex_junction",
            schema="public",
            columns=[
                make_column("user_id", DataTypeCategory.INTEGER, False),
                make_column("role_id", DataTypeCategory.INTEGER, False),
                make_column("extra_id", DataTypeCategory.INTEGER, False),
            ],
            primary_key=PrimaryKey(name="pk", columns=("user_id", "role_id")),
            foreign_keys=[
                ForeignKey(
                    name="fk1",
                    columns=("user_id",),
                    target_schema="public",
                    target_table="users",
                    target_columns=("id",),
                ),
                ForeignKey(
                    name="fk2",
                    columns=("role_id",),
                    target_schema="public",
                    target_table="roles",
                    target_columns=("id",),
                ),
                ForeignKey(
                    name="fk3",
                    columns=("extra_id",),
                    target_schema="public",
                    target_table="extras",
                    target_columns=("id",),
                ),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_junction_signals(table, graph)
        signal_names = {s.name for s in signals}
        assert "pk_subset_of_fks" in signal_names


class TestWideTableSignal:
    """Tests for wide_table signal in fact detection."""

    def test_wide_table_with_10_columns(self) -> None:
        """Table with >=10 columns should trigger wide_table signal."""
        columns = [
            make_column("id", DataTypeCategory.INTEGER, False, True),
            make_column("col1", DataTypeCategory.TEXT),
            make_column("col2", DataTypeCategory.TEXT),
            make_column("col3", DataTypeCategory.TEXT),
            make_column("col4", DataTypeCategory.TEXT),
            make_column("col5", DataTypeCategory.TEXT),
            make_column("col6", DataTypeCategory.TEXT),
            make_column("col7", DataTypeCategory.TEXT),
            make_column("col8", DataTypeCategory.TEXT),
            make_column("col9", DataTypeCategory.TEXT),
        ]
        table = make_table("wide_orders", columns=columns)
        graph = SchemaGraph.from_tables([table])

        signals = _detect_fact_signals(table, graph)
        signal_names = {s.name for s in signals}
        assert "wide_table" in signal_names


class TestSingleOutgoingFK:
    """Tests for single_outgoing_fk signal in dimension detection."""

    def test_dimension_with_one_fk(self) -> None:
        """Dimension with exactly one FK should trigger single_outgoing_fk."""
        table = make_table(
            "subcategory",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("category_id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
            ],
            fk_targets=[("category_id", "categories")],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_dimension_signals(table, graph)
        signal_names = {s.name for s in signals}
        assert "single_outgoing_fk" in signal_names


class TestSCDValidFromOnly:
    """Tests for valid_from_only signal."""

    def test_scd_with_only_valid_from(self) -> None:
        """Table with valid_from but no valid_to should get weaker signal."""
        table = make_table(
            "currency_rates",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("currency", DataTypeCategory.TEXT),
                make_column("rate", DataTypeCategory.DECIMAL),
                make_column("valid_from", DataTypeCategory.TIMESTAMP),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_scd_type2_signals(table, graph)
        signal_names = {s.name for s in signals}
        assert "valid_from_only" in signal_names
        assert "validity_period" not in signal_names


class TestVersionColumn:
    """Tests for version_column signal."""

    def test_scd_with_version_column(self) -> None:
        """Table with version column should trigger version_column signal."""
        table = make_table(
            "document_versions",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("document_id", DataTypeCategory.INTEGER),
                make_column("content", DataTypeCategory.TEXT),
                make_column("version", DataTypeCategory.INTEGER),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        signals = _detect_scd_type2_signals(table, graph)
        signal_names = {s.name for s in signals}
        assert "version_column" in signal_names


class TestDetectWithValidation:
    """Tests for detect_with_validation method."""

    def test_fact_referencing_dimensions_gets_boost(self) -> None:
        """Fact table referencing dimensions should get confidence boost."""
        # Create dimension tables
        customers = make_table(
            "customers",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("name", DataTypeCategory.TEXT),
                make_column("email", DataTypeCategory.TEXT),
                make_column("address", DataTypeCategory.TEXT),
            ],
        )
        products = make_table(
            "products",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("name", DataTypeCategory.TEXT),
                make_column("sku", DataTypeCategory.TEXT),
            ],
        )
        stores = make_table(
            "stores",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("name", DataTypeCategory.TEXT),
                make_column("location", DataTypeCategory.TEXT),
            ],
        )

        # Create fact table
        sales = make_table(
            "sales_facts",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("customer_id", DataTypeCategory.INTEGER),
                make_column("product_id", DataTypeCategory.INTEGER),
                make_column("store_id", DataTypeCategory.INTEGER),
                make_column("quantity", DataTypeCategory.INTEGER),
                make_column("amount", DataTypeCategory.DECIMAL),
            ],
            fk_targets=[
                ("customer_id", "customers"),
                ("product_id", "products"),
                ("store_id", "stores"),
            ],
        )

        graph = SchemaGraph.from_tables([customers, products, stores, sales])

        detector = RoleDetector()
        result = detector.detect_with_validation(sales, graph)

        assert result.primary_role == RoleType.FACT
        # Should have references_dimensions signal
        signal_names = {s.name for s in result.signals}
        assert "references_dimensions" in signal_names

    def test_non_fact_table_no_boost(self) -> None:
        """Non-fact tables should not get the dimension reference boost."""
        table = make_table(
            "customers",
            columns=[
                make_column("id", DataTypeCategory.INTEGER, False, True),
                make_column("name", DataTypeCategory.TEXT),
            ],
        )
        graph = SchemaGraph.from_tables([table])

        detector = RoleDetector()
        result = detector.detect_with_validation(table, graph)

        # Should not have references_dimensions (not a FACT)
        signal_names = {s.name for s in result.signals}
        assert "references_dimensions" not in signal_names
