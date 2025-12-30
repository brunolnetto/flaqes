"""Tests for schema graph data structures."""

import pytest

from flaqes.core.schema_graph import (
    Column,
    Constraint,
    DataType,
    ForeignKey,
    Index,
    PrimaryKey,
    SchemaGraph,
    Table,
)
from flaqes.core.types import (
    Cardinality,
    ConstraintType,
    DataTypeCategory,
    IndexMethod,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_column() -> Column:
    """Create a sample column."""
    return Column(
        name="id",
        data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER),
        nullable=False,
        is_identity=True,
        ordinal_position=1,
    )


@pytest.fixture
def sample_table() -> Table:
    """Create a sample table with various columns."""
    return Table(
        name="orders",
        schema="public",
        columns=[
            Column(
                name="id",
                data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER),
                nullable=False,
                is_identity=True,
                ordinal_position=1,
            ),
            Column(
                name="customer_id",
                data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER),
                nullable=False,
                ordinal_position=2,
            ),
            Column(
                name="created_at",
                data_type=DataType(
                    raw="timestamp with time zone",
                    category=DataTypeCategory.TIMESTAMP,
                ),
                nullable=False,
                ordinal_position=3,
            ),
            Column(
                name="metadata",
                data_type=DataType(raw="jsonb", category=DataTypeCategory.JSON),
                nullable=True,
                ordinal_position=4,
            ),
        ],
        primary_key=PrimaryKey(name="orders_pkey", columns=("id",)),
        foreign_keys=[
            ForeignKey(
                name="orders_customer_fk",
                columns=("customer_id",),
                target_schema="public",
                target_table="customers",
                target_columns=("id",),
            )
        ],
    )


@pytest.fixture
def customers_table() -> Table:
    """Create a customers table."""
    return Table(
        name="customers",
        schema="public",
        columns=[
            Column(
                name="id",
                data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER),
                nullable=False,
                is_identity=True,
            ),
            Column(
                name="name",
                data_type=DataType(raw="text", category=DataTypeCategory.TEXT),
                nullable=False,
            ),
        ],
        primary_key=PrimaryKey(name="customers_pkey", columns=("id",)),
    )


# =============================================================================
# DataType Tests
# =============================================================================


class TestDataType:
    """Tests for DataType class."""

    def test_str_returns_raw_type(self) -> None:
        dt = DataType(raw="character varying(255)", category=DataTypeCategory.TEXT)
        assert str(dt) == "character varying(255)"

    def test_array_type(self) -> None:
        dt = DataType(
            raw="integer[]",
            category=DataTypeCategory.ARRAY,
            is_array=True,
            element_type="integer",
        )
        assert dt.is_array
        assert dt.element_type == "integer"


# =============================================================================
# Column Tests
# =============================================================================


class TestColumn:
    """Tests for Column class."""

    def test_str_representation(self, sample_column: Column) -> None:
        assert "id" in str(sample_column)
        assert "integer" in str(sample_column)
        assert "NOT NULL" in str(sample_column)

    def test_nullable_column_str(self) -> None:
        col = Column(
            name="optional",
            data_type=DataType(raw="text", category=DataTypeCategory.TEXT),
            nullable=True,
        )
        assert "NOT NULL" not in str(col)


# =============================================================================
# PrimaryKey Tests
# =============================================================================


class TestPrimaryKey:
    """Tests for PrimaryKey class."""

    def test_single_column_pk_not_composite(self) -> None:
        pk = PrimaryKey(name="pk", columns=("id",))
        assert not pk.is_composite

    def test_multi_column_pk_is_composite(self) -> None:
        pk = PrimaryKey(name="pk", columns=("order_id", "product_id"))
        assert pk.is_composite


# =============================================================================
# ForeignKey Tests
# =============================================================================


class TestForeignKey:
    """Tests for ForeignKey class."""

    def test_single_column_fk_not_composite(self) -> None:
        fk = ForeignKey(
            name="fk",
            columns=("customer_id",),
            target_schema="public",
            target_table="customers",
            target_columns=("id",),
        )
        assert not fk.is_composite

    def test_composite_fk(self) -> None:
        fk = ForeignKey(
            name="fk",
            columns=("order_id", "line_num"),
            target_schema="public",
            target_table="order_lines",
            target_columns=("order_id", "line_num"),
        )
        assert fk.is_composite

    def test_target_fqn(self) -> None:
        fk = ForeignKey(
            name="fk",
            columns=("customer_id",),
            target_schema="sales",
            target_table="customers",
            target_columns=("id",),
        )
        assert fk.target_fqn == "sales.customers"


# =============================================================================
# Table Tests
# =============================================================================


class TestTable:
    """Tests for Table class."""

    def test_fqn(self, sample_table: Table) -> None:
        assert sample_table.fqn == "public.orders"

    def test_column_names(self, sample_table: Table) -> None:
        names = sample_table.column_names
        assert names == ["id", "customer_id", "created_at", "metadata"]

    def test_get_column(self, sample_table: Table) -> None:
        col = sample_table.get_column("created_at")
        assert col is not None
        assert col.name == "created_at"

    def test_get_column_not_found(self, sample_table: Table) -> None:
        col = sample_table.get_column("nonexistent")
        assert col is None

    def test_has_column(self, sample_table: Table) -> None:
        assert sample_table.has_column("id")
        assert not sample_table.has_column("nonexistent")

    def test_timestamp_columns(self, sample_table: Table) -> None:
        ts_cols = sample_table.timestamp_columns
        assert len(ts_cols) == 1
        assert ts_cols[0].name == "created_at"

    def test_json_columns(self, sample_table: Table) -> None:
        json_cols = sample_table.json_columns
        assert len(json_cols) == 1
        assert json_cols[0].name == "metadata"

    def test_has_surrogate_key(self, sample_table: Table) -> None:
        assert sample_table.has_surrogate_key

    def test_has_surrogate_key_false_for_composite(self) -> None:
        table = Table(
            name="order_items",
            columns=[
                Column(
                    name="order_id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
                Column(
                    name="item_id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
            ],
            primary_key=PrimaryKey(name="pk", columns=("order_id", "item_id")),
        )
        assert not table.has_surrogate_key

    def test_has_natural_key_composite(self) -> None:
        table = Table(
            name="subscriptions",
            columns=[
                Column(
                    name="user_id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
                Column(
                    name="plan_id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
            ],
            primary_key=PrimaryKey(name="pk", columns=("user_id", "plan_id")),
        )
        assert table.has_natural_key


# =============================================================================
# Index Tests
# =============================================================================


class TestIndex:
    """Tests for Index class."""

    def test_basic_index(self) -> None:
        idx = Index(
            name="idx_orders_customer",
            table_schema="public",
            table_name="orders",
            columns=("customer_id",),
        )
        assert not idx.is_unique
        assert not idx.is_partial
        assert idx.method == IndexMethod.BTREE

    def test_expression_index(self) -> None:
        idx = Index(
            name="idx_orders_lower_name",
            table_schema="public",
            table_name="orders",
            columns=(),
            expression_columns=("lower(name)",),
        )
        assert idx.is_expression_index


# =============================================================================
# SchemaGraph Tests
# =============================================================================


class TestSchemaGraph:
    """Tests for SchemaGraph class."""

    def test_add_and_get_table(self, sample_table: Table) -> None:
        graph = SchemaGraph()
        graph.add_table(sample_table)

        retrieved = graph.get_table("public.orders")
        assert retrieved is sample_table

    def test_get_table_by_name(self, sample_table: Table) -> None:
        graph = SchemaGraph()
        graph.add_table(sample_table)

        retrieved = graph.get_table_by_name("orders")
        assert retrieved is sample_table

    def test_len(self, sample_table: Table, customers_table: Table) -> None:
        graph = SchemaGraph()
        graph.add_table(sample_table)
        graph.add_table(customers_table)
        assert len(graph) == 2

    def test_iter(self, sample_table: Table, customers_table: Table) -> None:
        graph = SchemaGraph()
        graph.add_table(sample_table)
        graph.add_table(customers_table)

        tables = list(graph)
        assert len(tables) == 2

    def test_from_tables_builds_relationships(
        self, sample_table: Table, customers_table: Table
    ) -> None:
        graph = SchemaGraph.from_tables([sample_table, customers_table])

        assert len(graph.relationships) == 1
        rel = graph.relationships[0]
        assert rel.source_table == "public.orders"
        assert rel.target_table == "public.customers"

    def test_tables_referencing(
        self, sample_table: Table, customers_table: Table
    ) -> None:
        graph = SchemaGraph.from_tables([sample_table, customers_table])

        referencing = graph.tables_referencing("public.customers")
        assert len(referencing) == 1
        assert referencing[0].name == "orders"

    def test_tables_referenced_by(
        self, sample_table: Table, customers_table: Table
    ) -> None:
        graph = SchemaGraph.from_tables([sample_table, customers_table])

        referenced = graph.tables_referenced_by("public.orders")
        assert len(referenced) == 1
        assert referenced[0].name == "customers"

    def test_neighborhood(self, sample_table: Table, customers_table: Table) -> None:
        graph = SchemaGraph.from_tables([sample_table, customers_table])

        # Depth 1 from orders should include customers
        neighborhood = graph.neighborhood("public.orders", depth=1)
        assert "public.orders" in neighborhood
        assert "public.customers" in neighborhood


class TestRelationshipCardinality:
    """Tests for relationship cardinality inference."""

    def test_identifying_relationship_detected(self) -> None:
        """FK that is part of PK should be identifying."""
        order_items = Table(
            name="order_items",
            schema="public",
            columns=[
                Column(
                    name="order_id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
                Column(
                    name="item_num",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
            ],
            primary_key=PrimaryKey(name="pk", columns=("order_id", "item_num")),
            foreign_keys=[
                ForeignKey(
                    name="fk",
                    columns=("order_id",),
                    target_schema="public",
                    target_table="orders",
                    target_columns=("id",),
                )
            ],
        )

        orders = Table(
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

        graph = SchemaGraph.from_tables([order_items, orders])

        rel = graph.relationships[0]
        assert rel.is_identifying

    def test_unique_fk_is_one_to_one(self) -> None:
        """FK with unique constraint should be one-to-one."""
        profile = Table(
            name="user_profiles",
            schema="public",
            columns=[
                Column(
                    name="id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
                Column(
                    name="user_id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
            ],
            primary_key=PrimaryKey(name="pk", columns=("id",)),
            foreign_keys=[
                ForeignKey(
                    name="fk",
                    columns=("user_id",),
                    target_schema="public",
                    target_table="users",
                    target_columns=("id",),
                )
            ],
            constraints=[
                Constraint(
                    name="unique_user",
                    constraint_type=ConstraintType.UNIQUE,
                    columns=("user_id",),
                )
            ],
        )

        users = Table(
            name="users",
            schema="public",
            columns=[
                Column(
                    name="id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
            ],
            primary_key=PrimaryKey(name="pk", columns=("id",)),
        )

        graph = SchemaGraph.from_tables([profile, users])

        rel = graph.relationships[0]
        assert rel.cardinality == Cardinality.ONE_TO_ONE


# =============================================================================
# Additional Coverage Tests
# =============================================================================


class TestHasNaturalKey:
    """Tests for has_natural_key property."""

    def test_no_primary_key_returns_false(self) -> None:
        """Table without PK should not have natural key."""
        table = Table(
            name="heap_table",
            columns=[
                Column(
                    name="data",
                    data_type=DataType(raw="text", category=DataTypeCategory.TEXT),
                ),
            ],
            primary_key=None,
        )
        assert not table.has_natural_key

    def test_single_non_identity_pk_is_natural(self) -> None:
        """Single-column PK that is not identity should be natural key."""
        table = Table(
            name="products",
            columns=[
                Column(
                    name="sku",
                    data_type=DataType(raw="varchar", category=DataTypeCategory.TEXT),
                    nullable=False,
                    is_identity=False,
                    is_generated=False,
                ),
                Column(
                    name="name",
                    data_type=DataType(raw="text", category=DataTypeCategory.TEXT),
                ),
            ],
            primary_key=PrimaryKey(name="pk", columns=("sku",)),
        )
        assert table.has_natural_key

    def test_identity_pk_is_not_natural(self) -> None:
        """Identity column PK should not be natural key."""
        table = Table(
            name="users",
            columns=[
                Column(
                    name="id",
                    data_type=DataType(
                        raw="integer", category=DataTypeCategory.INTEGER
                    ),
                    nullable=False,
                    is_identity=True,
                ),
            ],
            primary_key=PrimaryKey(name="pk", columns=("id",)),
        )
        assert not table.has_natural_key


class TestNeighborhoodBidirectional:
    """Tests for neighborhood traversal in both directions."""

    def test_neighborhood_follows_reverse_direction(self) -> None:
        """Neighborhood should include tables that reference the source."""
        # A -> B (A references B)
        # Starting from B, we should find A
        table_a = Table(
            name="orders",
            schema="public",
            columns=[
                Column(
                    name="id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
                Column(
                    name="customer_id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
            ],
            primary_key=PrimaryKey(name="pk", columns=("id",)),
            foreign_keys=[
                ForeignKey(
                    name="fk",
                    columns=("customer_id",),
                    target_schema="public",
                    target_table="customers",
                    target_columns=("id",),
                )
            ],
        )
        table_b = Table(
            name="customers",
            schema="public",
            columns=[
                Column(
                    name="id",
                    data_type=DataType(raw="int", category=DataTypeCategory.INTEGER),
                ),
            ],
            primary_key=PrimaryKey(name="pk", columns=("id",)),
        )

        graph = SchemaGraph.from_tables([table_a, table_b])

        # Starting from customers, should find orders via reverse FK
        neighborhood = graph.neighborhood("public.customers", depth=1)
        assert "public.customers" in neighborhood
        assert "public.orders" in neighborhood
