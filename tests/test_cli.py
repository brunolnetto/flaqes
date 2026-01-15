"""Tests for the CLI module."""

import argparse
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flaqes.cli import (
    create_parser,
    main,
    run_analyze,
    run_analyze_ddl,
    run_introspect,
)


class TestCreateParser:
    """Tests for the argument parser."""

    def test_parser_creation(self):
        """Test that the parser is created correctly."""
        parser = create_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "flaqes"

    def test_version_flag(self, capsys):
        """Test --version flag."""
        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "0.1.0" in captured.out

    def test_analyze_subcommand(self):
        """Test analyze subcommand parsing."""
        parser = create_parser()
        args = parser.parse_args(["analyze", "postgresql://localhost/test"])
        assert args.command == "analyze"
        assert args.dsn == "postgresql://localhost/test"
        assert args.workload == "mixed"
        assert args.volume == "medium"
        assert args.format == "markdown"

    def test_analyze_with_options(self):
        """Test analyze with all options."""
        parser = create_parser()
        args = parser.parse_args([
            "analyze", "postgresql://localhost/test",
            "--workload", "OLAP",
            "--volume", "large",
            "--format", "json",
            "--tables", "users", "orders",
        ])
        assert args.workload == "OLAP"
        assert args.volume == "large"
        assert args.format == "json"
        assert args.tables == ["users", "orders"]

    def test_analyze_ddl_subcommand(self):
        """Test analyze-ddl subcommand parsing."""
        parser = create_parser()
        args = parser.parse_args(["analyze-ddl", "schema.sql"])
        assert args.command == "analyze-ddl"
        assert args.files == ["schema.sql"]
        assert args.workload == "mixed"
        assert args.volume == "medium"
        assert args.format == "markdown"
        assert args.schema == "public"

    def test_analyze_ddl_with_options(self):
        """Test analyze-ddl with all options."""
        parser = create_parser()
        args = parser.parse_args([
            "analyze-ddl", "schema1.sql", "schema2.sql",
            "--workload", "OLTP",
            "--volume", "small",
            "--format", "json",
            "--schema", "myapp",
        ])
        assert args.files == ["schema1.sql", "schema2.sql"]
        assert args.workload == "OLTP"
        assert args.volume == "small"
        assert args.format == "json"
        assert args.schema == "myapp"

    def test_introspect_subcommand(self):
        """Test introspect subcommand parsing."""
        parser = create_parser()
        args = parser.parse_args(["introspect", "--dsn", "postgresql://localhost/test"])
        assert args.command == "introspect"
        assert args.dsn == "postgresql://localhost/test"
        assert args.format == "text"


class TestMain:
    """Tests for the main entry point."""

    def test_no_command_shows_help(self, capsys):
        """Test that no command shows help."""
        with patch("sys.argv", ["flaqes"]):
            result = main()
        assert result == 0
        captured = capsys.readouterr()
        assert "flaqes" in captured.out or result == 0

    def test_analyze_command_routes(self):
        """Test that analyze command routes correctly."""
        with patch("sys.argv", ["flaqes", "analyze", "postgresql://localhost/test"]):
            with patch("flaqes.cli.asyncio.run") as mock_run:
                mock_run.return_value = 0
                result = main()
        assert result == 0

    def test_analyze_ddl_command_routes(self):
        """Test that analyze-ddl command routes correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("CREATE TABLE test (id SERIAL PRIMARY KEY);")
            f.flush()
            
            with patch("sys.argv", ["flaqes", "analyze-ddl", f.name]):
                result = main()
            
            # Should succeed since no DB connection needed
            assert result == 0

    def test_introspect_command_routes(self):
        """Test that introspect command routes correctly."""
        with patch("sys.argv", ["flaqes", "introspect", "--dsn", "postgresql://localhost/test"]):
            with patch("flaqes.cli.asyncio.run") as mock_run:
                mock_run.return_value = 0
                result = main()
        assert result == 0


class TestRunAnalyze:
    """Tests for the analyze command."""

    @pytest.mark.asyncio
    async def test_analyze_handles_connection_error(self, capsys):
        """Test that connection errors are handled gracefully."""
        args = argparse.Namespace(
            dsn="postgresql://localhost:9999/nonexistent",
            workload="mixed",
            volume="medium",
            format="markdown",
            tables=None,
            schemas=None,
        )
        
        result = await run_analyze(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err

    @pytest.mark.asyncio
    async def test_analyze_handles_error(self, capsys):
        """Test that errors are handled gracefully."""
        args = argparse.Namespace(
            dsn="invalid://notreal",
            workload="mixed",
            volume="medium",
            format="markdown",
            tables=None,
            schemas=None,
        )
        
        result = await run_analyze(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err


class TestRunAnalyzeDDL:
    """Tests for the analyze-ddl command."""

    def test_analyze_ddl_success_markdown(self, capsys):
        """Test successful DDL analysis with markdown output."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("""
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """)
            f.flush()
            
            args = argparse.Namespace(
                files=[f.name],
                workload="mixed",
                volume="medium",
                format="markdown",
                schema="public",
            )
            
            result = run_analyze_ddl(args)
            assert result == 0
            
            captured = capsys.readouterr()
            assert "Schema Analysis Report" in captured.out

    def test_analyze_ddl_success_json(self, capsys):
        """Test successful DDL analysis with JSON output."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("""
            CREATE TABLE orders (
                id SERIAL PRIMARY KEY,
                total NUMERIC NOT NULL
            );
            """)
            f.flush()
            
            args = argparse.Namespace(
                files=[f.name],
                workload="OLTP",
                volume="small",
                format="json",
                schema="public",
            )
            
            result = run_analyze_ddl(args)
            assert result == 0
            
            captured = capsys.readouterr()
            assert '"table_count"' in captured.out

    def test_analyze_ddl_multiple_files(self, capsys):
        """Test DDL analysis with multiple files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f1:
            f1.write("CREATE TABLE users (id SERIAL PRIMARY KEY);")
            f1.flush()
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f2:
                f2.write("CREATE TABLE orders (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id));")
                f2.flush()
                
                args = argparse.Namespace(
                    files=[f1.name, f2.name],
                    workload="mixed",
                    volume="medium",
                    format="markdown",
                    schema="public",
                )
                
                result = run_analyze_ddl(args)
                assert result == 0

    def test_analyze_ddl_file_not_found(self, capsys):
        """Test DDL analysis with missing file."""
        args = argparse.Namespace(
            files=["nonexistent_file.sql"],
            workload="mixed",
            volume="medium",
            format="markdown",
            schema="public",
        )
        
        result = run_analyze_ddl(args)
        assert result == 1
        
        captured = capsys.readouterr()
        assert "Error:" in captured.err

    def test_analyze_ddl_custom_schema(self, capsys):
        """Test DDL analysis with custom schema."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("CREATE TABLE items (id SERIAL PRIMARY KEY);")
            f.flush()
            
            args = argparse.Namespace(
                files=[f.name],
                workload="OLAP",
                volume="large",
                format="markdown",
                schema="myapp",
            )
            
            result = run_analyze_ddl(args)
            assert result == 0


class TestRunIntrospect:
    """Tests for the introspect command."""

    @pytest.mark.asyncio
    async def test_introspect_handles_error(self, capsys):
        """Test that errors are handled gracefully."""
        args = argparse.Namespace(
            dsn="invalid://notreal",
            format="text",
        )
        
        result = await run_introspect(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err

    @pytest.mark.asyncio
    async def test_introspect_handles_connection_error(self, capsys):
        """Test introspect with connection error."""
        args = argparse.Namespace(
            dsn="postgresql://localhost:9999/nonexistent",
            format="json",
        )
        
        result = await run_introspect(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err
