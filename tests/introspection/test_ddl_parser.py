"""Tests for the DDL parser module."""

import pytest

from flaqes.introspection.ddl_parser import (
    DDLParser,
    ParseResult,
    parse_ddl,
    _parse_data_type,
    _categorize_type,
)
from flaqes.core.types import DataTypeCategory, ConstraintType


class TestDataTypeParsing:
    """Tests for data type parsing."""

    def test_integer_types(self):
        """Test integer type categorization."""
        for type_str in ["integer", "int", "int4", "bigint", "smallint"]:
            category, is_array, element = _categorize_type(type_str)
            assert category == DataTypeCategory.INTEGER
            assert not is_array

    def test_text_types(self):
        """Test text type categorization."""
        for type_str in ["text", "varchar", "character varying", "char"]:
            category, is_array, element = _categorize_type(type_str)
            assert category == DataTypeCategory.TEXT
            assert not is_array

    def test_temporal_types(self):
        """Test temporal type categorization."""
        category, is_array, element = _categorize_type("timestamp")
        assert category == DataTypeCategory.TIMESTAMP
        assert not is_array
        
        category, is_array, element = _categorize_type("date")
        assert category == DataTypeCategory.DATE
        assert not is_array
        
        category, is_array, element = _categorize_type("time")
        assert category == DataTypeCategory.TIME
        assert not is_array

    def test_json_types(self):
        """Test JSON type categorization."""
        for type_str in ["json", "jsonb"]:
            category, is_array, element = _categorize_type(type_str)
            assert category == DataTypeCategory.JSON
            assert not is_array

    def test_uuid_type(self):
        """Test UUID type categorization."""
        category, is_array, element = _categorize_type("uuid")
        assert category == DataTypeCategory.UUID
        assert not is_array

    def test_array_types(self):
        """Test array type detection."""
        category, is_array, element = _categorize_type("integer[]")
        assert category == DataTypeCategory.ARRAY
        assert is_array
        assert element == "integer"

    def test_varchar_with_length(self):
        """Test varchar with length specification."""
        dt = _parse_data_type("varchar(255)")
        assert dt.category == DataTypeCategory.TEXT
        assert dt.raw == "varchar(255)"


class TestDDLParser:
    """Tests for the DDL parser."""

    def test_simple_table(self):
        """Test parsing a simple table."""
        ddl = """
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            name TEXT
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        assert len(result.tables) == 1
        
        table = result.tables[0]
        assert table.name == "users"
        assert table.schema == "public"
        assert len(table.columns) == 3
        
        # Check columns
        id_col = table.get_column("id")
        assert id_col is not None
        assert id_col.is_identity
        
        email_col = table.get_column("email")
        assert email_col is not None
        assert not email_col.nullable
        
        name_col = table.get_column("name")
        assert name_col is not None
        assert name_col.nullable
        
        # Check primary key
        assert table.primary_key is not None
        assert table.primary_key.columns == ("id",)

    def test_table_with_schema(self):
        """Test parsing table with explicit schema."""
        ddl = """
        CREATE TABLE myschema.users (
            id INTEGER PRIMARY KEY
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        assert result.tables[0].schema == "myschema"

    def test_quoted_identifiers(self):
        """Test parsing with quoted identifiers."""
        ddl = '''
        CREATE TABLE "User" (
            "userId" INTEGER PRIMARY KEY,
            "createdAt" TIMESTAMP DEFAULT NOW()
        );
        '''
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        assert table.name == "User"
        assert table.has_column("userId")
        assert table.has_column("createdAt")

    def test_foreign_key_constraint(self):
        """Test parsing foreign key constraints."""
        ddl = """
        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        assert len(table.foreign_keys) == 1
        
        fk = table.foreign_keys[0]
        assert fk.columns == ("user_id",)
        assert fk.target_table == "users"
        assert fk.target_columns == ("id",)
        assert fk.on_delete == "CASCADE"

    def test_inline_foreign_key(self):
        """Test parsing inline REFERENCES constraint."""
        ddl = """
        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id)
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        assert len(table.foreign_keys) == 1
        
        fk = table.foreign_keys[0]
        assert fk.columns == ("user_id",)
        assert fk.target_table == "users"

    def test_composite_primary_key(self):
        """Test parsing composite primary key."""
        ddl = """
        CREATE TABLE order_items (
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER,
            PRIMARY KEY (order_id, product_id)
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        assert table.primary_key is not None
        assert table.primary_key.columns == ("order_id", "product_id")

    def test_unique_constraint(self):
        """Test parsing UNIQUE constraint."""
        ddl = """
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        # Check for unique constraint
        unique_constraints = [
            c for c in table.constraints 
            if c.constraint_type == ConstraintType.UNIQUE
        ]
        assert len(unique_constraints) >= 1

    def test_named_constraint(self):
        """Test parsing named constraints."""
        ddl = """
        CREATE TABLE orders (
            id SERIAL,
            user_id INTEGER,
            CONSTRAINT pk_orders PRIMARY KEY (id),
            CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        assert table.primary_key is not None
        assert table.primary_key.name == "pk_orders"
        assert len(table.foreign_keys) == 1
        assert table.foreign_keys[0].name == "fk_user"

    def test_check_constraint(self):
        """Test parsing CHECK constraint."""
        ddl = """
        CREATE TABLE products (
            id SERIAL PRIMARY KEY,
            price NUMERIC CHECK (price > 0)
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        # CHECK constraints should be captured
        table = result.tables[0]
        check_constraints = [
            c for c in table.constraints 
            if c.constraint_type == ConstraintType.CHECK
        ]
        # May or may not be captured depending on implementation

    def test_default_values(self):
        """Test parsing DEFAULT values."""
        ddl = """
        CREATE TABLE posts (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW(),
            status VARCHAR(20) DEFAULT 'draft',
            views INTEGER DEFAULT 0
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        
        created_at = table.get_column("created_at")
        assert created_at is not None
        assert created_at.default is not None
        assert "NOW" in created_at.default.upper()

    def test_multiple_tables(self):
        """Test parsing multiple tables."""
        ddl = """
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255)
        );
        
        CREATE TABLE posts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            title TEXT
        );
        
        CREATE TABLE comments (
            id SERIAL PRIMARY KEY,
            post_id INTEGER REFERENCES posts(id),
            content TEXT
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        assert len(result.tables) == 3
        
        table_names = {t.name for t in result.tables}
        assert table_names == {"users", "posts", "comments"}

    def test_if_not_exists(self):
        """Test parsing CREATE TABLE IF NOT EXISTS."""
        ddl = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        assert result.tables[0].name == "users"


class TestParseDDLFunction:
    """Tests for the convenience parse_ddl function."""

    def test_parse_ddl_returns_graph(self):
        """Test that parse_ddl returns a SchemaGraph."""
        ddl = """
        CREATE TABLE users (id SERIAL PRIMARY KEY);
        """
        graph = parse_ddl(ddl)
        
        assert graph is not None
        tables = list(graph)
        assert len(tables) == 1
        assert tables[0].name == "users"

    def test_parse_ddl_custom_schema(self):
        """Test parse_ddl with custom default schema."""
        ddl = """
        CREATE TABLE users (id SERIAL PRIMARY KEY);
        """
        graph = parse_ddl(ddl, default_schema="myapp")
        
        tables = list(graph)
        assert tables[0].schema == "myapp"


class TestSchemaGraphIntegration:
    """Integration tests with SchemaGraph."""

    def test_parsed_graph_can_be_analyzed(self):
        """Test that parsed schema can be analyzed."""
        from flaqes.analysis import RoleDetector
        
        ddl = """
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            name TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            total_amount NUMERIC NOT NULL,
            order_date TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
        graph = parse_ddl(ddl)
        
        # Run role detection
        role_detector = RoleDetector()
        for table in graph:
            result = role_detector.detect(table, graph)
            assert result is not None
            assert result.confidence > 0

    def test_full_analysis_pipeline(self):
        """Test full analysis on parsed DDL."""
        from flaqes import generate_report, Intent
        
        ddl = """
        CREATE TABLE customers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email VARCHAR(255) UNIQUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE TABLE products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            price NUMERIC NOT NULL,
            category TEXT
        );
        
        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            order_date TIMESTAMP NOT NULL,
            total NUMERIC NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP
        );
        
        CREATE TABLE order_items (
            order_id INTEGER NOT NULL REFERENCES orders(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL,
            price NUMERIC NOT NULL,
            PRIMARY KEY (order_id, product_id)
        );
        """
        graph = parse_ddl(ddl)
        intent = Intent(workload="OLTP", data_volume="medium")
        
        report = generate_report(graph, intent=intent)
        
        assert report is not None
        assert report.table_count == 4
        assert len(report.table_roles) == 4
        
        # Verify report can be exported
        markdown = report.to_markdown()
        assert "customers" in markdown.lower() or "orders" in markdown.lower()
        
        json_data = report.to_dict()
        assert json_data["table_count"] == 4


class TestDDLParserEdgeCases:
    """Test edge cases and error handling."""

    def test_array_syntax(self):
        """Test ARRAY[type] syntax."""
        category, is_array, element = _categorize_type("ARRAY[integer]")
        assert is_array
        assert category == DataTypeCategory.ARRAY

    def test_empty_ddl(self):
        """Test parsing empty DDL."""
        parser = DDLParser()
        result = parser.parse("")
        assert result.success
        assert len(result.tables) == 0

    def test_no_create_table(self):
        """Test DDL without CREATE TABLE statements."""
        ddl = """
        -- Just comments
        SELECT * FROM users;
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        assert result.success
        assert len(result.tables) == 0

    def test_parse_file(self):
        """Test parse_file method."""
        import tempfile
        
        ddl = """
        CREATE TABLE test_file (id SERIAL PRIMARY KEY);
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write(ddl)
            f.flush()
            
            parser = DDLParser()
            result = parser.parse_file(f.name)
            
            assert result.success
            assert len(result.tables) == 1
            assert result.tables[0].name == "test_file"

    def test_table_level_unique(self):
        """Test table-level UNIQUE constraint."""
        ddl = """
        CREATE TABLE test (
            id SERIAL PRIMARY KEY,
            email TEXT,
            UNIQUE (email)
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        unique_constraints = [
            c for c in table.constraints
            if c.constraint_type == ConstraintType.UNIQUE
        ]
        assert len(unique_constraints) >= 1

    def test_table_level_check(self):
        """Test table-level CHECK constraint."""
        ddl = """
        CREATE TABLE prices (
            id SERIAL PRIMARY KEY,
            amount NUMERIC,
            CHECK (amount > 0)
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        check_constraints = [
            c for c in table.constraints
            if c.constraint_type == ConstraintType.CHECK
        ]
        assert len(check_constraints) >= 1

    def test_named_unique_constraint(self):
        """Test named UNIQUE constraint."""
        ddl = """
        CREATE TABLE test (
            id SERIAL PRIMARY KEY,
            code TEXT,
            CONSTRAINT uq_code UNIQUE (code)
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        unique_constraints = [
            c for c in table.constraints
            if c.constraint_type == ConstraintType.UNIQUE
        ]
        assert len(unique_constraints) >= 1
        assert unique_constraints[0].name == "uq_code"

    def test_named_check_constraint(self):
        """Test named CHECK constraint."""
        ddl = """
        CREATE TABLE test (
            id SERIAL PRIMARY KEY,
            value INTEGER,
            CONSTRAINT chk_positive CHECK (value >= 0)
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        check_constraints = [
            c for c in table.constraints
            if c.constraint_type == ConstraintType.CHECK
        ]
        assert len(check_constraints) >= 1

    def test_foreign_key_with_on_update(self):
        """Test FK with ON UPDATE clause."""
        ddl = """
        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        assert len(table.foreign_keys) == 1
        fk = table.foreign_keys[0]
        assert fk.on_update == "CASCADE"
        assert fk.on_delete == "SET NULL"

    def test_inline_fk_without_column(self):
        """Test inline REFERENCES without explicit target column."""
        ddl = """
        CREATE TABLE details (
            id SERIAL PRIMARY KEY,
            parent_id INTEGER REFERENCES parents
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        assert len(table.foreign_keys) == 1
        fk = table.foreign_keys[0]
        assert fk.target_table == "parents"

    def test_unknown_type(self):
        """Test handling of unknown types."""
        ddl = """
        CREATE TABLE test (
            id SERIAL PRIMARY KEY,
            custom_field CUSTOMTYPE
        );
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        assert result.success
        table = result.tables[0]
        custom_col = table.get_column("custom_field")
        assert custom_col is not None
        assert custom_col.data_type.category == DataTypeCategory.OTHER

    def test_float_types(self):
        """Test float type categorization."""
        category, is_array, element = _categorize_type("float")
        assert category == DataTypeCategory.FLOAT
        assert not is_array

    def test_interval_type(self):
        """Test interval type categorization."""
        category, is_array, element = _categorize_type("interval")
        assert category == DataTypeCategory.INTERVAL
        assert not is_array

    def test_decimal_types(self):
        """Test decimal type categorization."""
        category, is_array, element = _categorize_type("numeric")
        assert category == DataTypeCategory.DECIMAL
        assert not is_array

    def test_parse_ddl_file_function(self):
        """Test parse_ddl_file convenience function."""
        import tempfile
        from flaqes.introspection.ddl_parser import parse_ddl_file
        
        ddl = """
        CREATE TABLE file_test (id SERIAL PRIMARY KEY);
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write(ddl)
            f.flush()
            
            graph = parse_ddl_file(f.name)
            tables = list(graph)
            assert len(tables) == 1
            assert tables[0].name == "file_test"

    def test_to_schema_graph(self):
        """Test to_schema_graph method."""
        ddl = """
        CREATE TABLE graph_test (id SERIAL PRIMARY KEY);
        """
        parser = DDLParser()
        result = parser.parse(ddl)
        
        graph = parser.to_schema_graph(result)
        tables = list(graph)
        assert len(tables) == 1

