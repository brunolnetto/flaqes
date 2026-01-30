"""Tests for Mermaid diagram generation."""

from flaqes.core.schema_graph import (
    Column,
    DataType,
    ForeignKey,
    PrimaryKey,
    SchemaGraph,
    Table,
)
from flaqes.core.types import DataTypeCategory
from flaqes.report.mermaid import generate_mermaid_erd


def test_generate_mermaid_erd_simple():
    """Should generate valid Mermaid ERD for simple schema."""
    # Create simple schema: users -> orders
    users_table = Table(
        name="users",
        schema="public",
        columns=[
            Column(
                name="id",
                data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER),
                nullable=False,
            ),
            Column(
                name="email",
                data_type=DataType(raw="varchar", category=DataTypeCategory.TEXT),
                nullable=False,
            ),
        ],
        primary_key=PrimaryKey(name="users_pkey", columns=("id",)),
    )
    
    orders_table = Table(
        name="orders",
        schema="public",
        columns=[
            Column(
                name="id",
                data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER),
                nullable=False,
            ),
            Column(
                name="user_id",
                data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER),
                nullable=False,
            ),
            Column(
                name="total",
                data_type=DataType(raw="decimal", category=DataTypeCategory.DECIMAL),
                nullable=True,
            ),
        ],
        primary_key=PrimaryKey(name="orders_pkey", columns=("id",)),
        foreign_keys=[
            ForeignKey(
                name="orders_user_id_fkey",
                columns=("user_id",),
                target_table="users",
                target_schema="public",
                target_columns=("id",),
            )
        ],
    )
    
    graph = SchemaGraph(tables={"public.users": users_table, "public.orders": orders_table})
    
    mermaid = generate_mermaid_erd(graph)
    
    # Basic structure checks
    assert mermaid.startswith("erDiagram")
    assert "users {" in mermaid
    assert "orders {" in mermaid
    assert "integer id" in mermaid
    assert "varchar email" in mermaid
    assert "users ||--|{ orders" in mermaid or "users ||--o{ orders" in mermaid


def test_generate_mermaid_erd_nullable_fk():
    """Should use correct relationship notation for nullable FKs."""
    parent_table = Table(
        name="categories",
        schema="public",
        columns=[
            Column(
                name="id",
                data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER),
                nullable=False,
            ),
        ],
        primary_key=PrimaryKey(name="categories_pkey", columns=("id",)),
    )
    
    child_table = Table(
        name="products",
        schema="public",
        columns=[
            Column(
                name="id",
                data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER),
                nullable=False,
            ),
            Column(
                name="category_id",
                data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER),
                nullable=True,  # Nullable FK
            ),
        ],
        primary_key=PrimaryKey(name="products_pkey", columns=("id",)),
        foreign_keys=[
            ForeignKey(
                name="products_category_id_fkey",
                columns=("category_id",),
                target_table="categories",
                target_schema="public",
                target_columns=("id",),
            )
        ],
    )
    
    graph = SchemaGraph(tables={"public.categories": parent_table, "public.products": child_table})
    
    mermaid = generate_mermaid_erd(graph)
    
    # Nullable FK should use ||--o{ (optional)
    assert "categories ||--o{ products" in mermaid
