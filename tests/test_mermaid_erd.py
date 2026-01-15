"""Tests for Mermaid ERD diagram generation."""

import pytest

from flaqes.core.schema_graph import (
    Column,
    Constraint,
    DataType,
    ForeignKey,
    PrimaryKey,
    SchemaGraph,
    Table,
)
from flaqes.core.types import ConstraintType, DataTypeCategory


class TestMermaidERD:
    """Test cases for SchemaGraph.to_mermaid_erd method."""

    def test_simple_table(self) -> None:
        """Test ERD generation for a simple table."""
        table = Table(
            name="users",
            schema="public",
            columns=[
                Column(name="id", data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER)),
                Column(name="email", data_type=DataType(raw="varchar(255)", category=DataTypeCategory.TEXT)),
                Column(name="name", data_type=DataType(raw="text", category=DataTypeCategory.TEXT)),
            ],
            primary_key=PrimaryKey(name="users_pkey", columns=("id",)),
        )
        
        graph = SchemaGraph.from_tables([table])
        mermaid = graph.to_mermaid_erd()
        
        assert "erDiagram" in mermaid
        assert "users {" in mermaid
        assert 'int id "PK"' in mermaid
        assert "varchar email" in mermaid
        assert "text name" in mermaid

    def test_table_with_foreign_key(self) -> None:
        """Test ERD generation with foreign key relationships."""
        users = Table(
            name="users",
            schema="public",
            columns=[
                Column(name="id", data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER)),
            ],
            primary_key=PrimaryKey(name="users_pkey", columns=("id",)),
        )
        
        orders = Table(
            name="orders",
            schema="public",
            columns=[
                Column(name="id", data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER)),
                Column(name="user_id", data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER)),
            ],
            primary_key=PrimaryKey(name="orders_pkey", columns=("id",)),
            foreign_keys=[
                ForeignKey(
                    name="orders_user_fk",
                    columns=("user_id",),
                    target_schema="public",
                    target_table="users",
                    target_columns=("id",),
                ),
            ],
        )
        
        graph = SchemaGraph.from_tables([users, orders])
        mermaid = graph.to_mermaid_erd()
        
        assert "erDiagram" in mermaid
        assert "users {" in mermaid
        assert "orders {" in mermaid
        assert 'int user_id "FK"' in mermaid
        assert '}o--|| users : "user_id"' in mermaid

    def test_table_with_unique_constraint(self) -> None:
        """Test ERD generation with unique constraints."""
        table = Table(
            name="users",
            schema="public",
            columns=[
                Column(name="id", data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER)),
                Column(name="email", data_type=DataType(raw="varchar(255)", category=DataTypeCategory.TEXT)),
            ],
            primary_key=PrimaryKey(name="users_pkey", columns=("id",)),
            constraints=[
                Constraint(
                    name="users_email_key",
                    constraint_type=ConstraintType.UNIQUE,
                    columns=("email",),
                ),
            ],
        )
        
        graph = SchemaGraph.from_tables([table])
        mermaid = graph.to_mermaid_erd()
        
        assert 'varchar email "UK"' in mermaid

    def test_no_columns_option(self) -> None:
        """Test ERD generation without columns."""
        table = Table(
            name="users",
            schema="public",
            columns=[
                Column(name="id", data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER)),
            ],
        )
        
        graph = SchemaGraph.from_tables([table])
        mermaid = graph.to_mermaid_erd(include_columns=False)
        
        assert "erDiagram" in mermaid
        assert "users" in mermaid
        assert "{" not in mermaid  # No column block

    def test_no_types_option(self) -> None:
        """Test ERD generation without types."""
        table = Table(
            name="users",
            schema="public",
            columns=[
                Column(name="id", data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER)),
            ],
            primary_key=PrimaryKey(name="users_pkey", columns=("id",)),
        )
        
        graph = SchemaGraph.from_tables([table])
        mermaid = graph.to_mermaid_erd(show_types=False)
        
        assert "erDiagram" in mermaid
        assert "id" in mermaid
        # Type should not appear before column name
        lines = [l for l in mermaid.split("\n") if "id" in l]
        assert any('id "PK"' in l for l in lines)

    def test_max_columns_limit(self) -> None:
        """Test that max_columns limits the displayed columns."""
        columns = [
            Column(name=f"col{i}", data_type=DataType(raw="text", category=DataTypeCategory.TEXT))
            for i in range(15)
        ]
        
        table = Table(name="wide_table", schema="public", columns=columns)
        graph = SchemaGraph.from_tables([table])
        
        mermaid = graph.to_mermaid_erd(max_columns=5)
        
        assert "col0" in mermaid
        assert "col4" in mermaid
        assert "col5" not in mermaid
        assert "+10 more" in mermaid

    def test_all_columns_by_default(self) -> None:
        """Test that all columns are shown by default (max_columns=None)."""
        columns = [
            Column(name=f"col{i}", data_type=DataType(raw="text", category=DataTypeCategory.TEXT))
            for i in range(15)
        ]
        
        table = Table(name="wide_table", schema="public", columns=columns)
        graph = SchemaGraph.from_tables([table])
        
        mermaid = graph.to_mermaid_erd()  # Default is max_columns=None
        
        # All columns should be shown
        assert "col0" in mermaid
        assert "col14" in mermaid
        assert "+more" not in mermaid

    def test_type_simplification(self) -> None:
        """Test that types are simplified correctly."""
        table = Table(
            name="test",
            schema="public",
            columns=[
                Column(name="c1", data_type=DataType(raw="character varying(255)", category=DataTypeCategory.TEXT)),
                Column(name="c2", data_type=DataType(raw="timestamp without time zone", category=DataTypeCategory.TIMESTAMP)),
                Column(name="c3", data_type=DataType(raw="double precision", category=DataTypeCategory.FLOAT)),
                Column(name="c4", data_type=DataType(raw="boolean", category=DataTypeCategory.BOOLEAN)),
            ],
        )
        
        graph = SchemaGraph.from_tables([table])
        mermaid = graph.to_mermaid_erd()
        
        assert "varchar c1" in mermaid
        assert "timestamp c2" in mermaid
        assert "double c3" in mermaid
        assert "bool c4" in mermaid

    def test_empty_graph(self) -> None:
        """Test ERD generation for empty graph."""
        graph = SchemaGraph()
        mermaid = graph.to_mermaid_erd()
        
        assert mermaid == "erDiagram"

    def test_composite_primary_key(self) -> None:
        """Test ERD with composite primary key."""
        table = Table(
            name="order_items",
            schema="public",
            columns=[
                Column(name="order_id", data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER)),
                Column(name="product_id", data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER)),
                Column(name="quantity", data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER)),
            ],
            primary_key=PrimaryKey(name="order_items_pkey", columns=("order_id", "product_id")),
        )
        
        graph = SchemaGraph.from_tables([table])
        mermaid = graph.to_mermaid_erd()
        
        assert 'int order_id "PK"' in mermaid
        assert 'int product_id "PK"' in mermaid

    def test_one_to_one_relationship(self) -> None:
        """Test ERD with one-to-one relationship (FK is also unique)."""
        users = Table(
            name="users",
            schema="public",
            columns=[
                Column(name="id", data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER)),
            ],
            primary_key=PrimaryKey(name="users_pkey", columns=("id",)),
        )
        
        # profile has unique FK to users - making it one-to-one
        profile = Table(
            name="profile",
            schema="public",
            columns=[
                Column(name="id", data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER)),
                Column(name="user_id", data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER)),
            ],
            primary_key=PrimaryKey(name="profile_pkey", columns=("id",)),
            foreign_keys=[
                ForeignKey(
                    name="profile_user_fk",
                    columns=("user_id",),
                    target_schema="public",
                    target_table="users",
                    target_columns=("id",),
                ),
            ],
            constraints=[
                Constraint(
                    name="profile_user_unique",
                    constraint_type=ConstraintType.UNIQUE,
                    columns=("user_id",),
                ),
            ],
        )
        
        graph = SchemaGraph.from_tables([users, profile])
        mermaid = graph.to_mermaid_erd()
        
        # One-to-one uses ||--||
        assert "||--||" in mermaid
