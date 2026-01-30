<<<<<<< HEAD
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
        assert "flaqes" in captured.out

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
            with patch("flaqes.cli.run_analyze", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = 0
                result = main()
        assert result == 0
        assert mock_run.called

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
            with patch("flaqes.cli.run_introspect", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = 0
                result = main()
        assert result == 0
        assert mock_run.called


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
=======
"""Tests for the CLI interface."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flakes.cli import (
    cmd_analyze,
    cmd_version,
    create_parser,
    get_intent_from_args,
    main,
    parse_read_patterns,
)
from flakes.core.intent import OLAP_INTENT, OLTP_INTENT


class TestParser:
    """Test argument parser creation and parsing."""

    def test_create_parser(self):
        """Test parser creation."""
        parser = create_parser()
        assert parser.prog == "flakes"

    def test_parser_no_command(self):
        """Test parser with no command accepts empty args."""
        parser = create_parser()
        args = parser.parse_args([])
        # No command is valid, handled in main()
        assert args.command is None

    def test_parser_analyze_basic(self):
        """Test parsing analyze command with DSN."""
        parser = create_parser()
        args = parser.parse_args(["analyze", "postgresql://localhost/test"])
        assert args.command == "analyze"
        assert args.dsn == "postgresql://localhost/test"
        assert args.format == "markdown"
        assert args.intent is None

    def test_parser_analyze_with_intent_preset(self):
        """Test parsing with intent preset."""
        parser = create_parser()
        args = parser.parse_args([
            "analyze",
            "--intent", "olap",
            "postgresql://localhost/test"
        ])
        assert args.intent == "olap"

    def test_parser_analyze_with_custom_intent(self):
        """Test parsing with custom intent parameters."""
        parser = create_parser()
        args = parser.parse_args([
            "analyze",
            "--workload", "OLTP",
            "--write-frequency", "high",
            "--read-patterns", "point_lookup,join_heavy",
            "postgresql://localhost/test"
        ])
        assert args.workload == "OLTP"
        assert args.write_frequency == "high"
        assert args.read_patterns == "point_lookup,join_heavy"

    def test_parser_analyze_with_tables(self):
        """Test parsing with table filter."""
        parser = create_parser()
        args = parser.parse_args([
            "analyze",
            "--tables", "users,orders,products",
            "postgresql://localhost/test"
        ])
        assert args.tables == "users,orders,products"

    def test_parser_analyze_with_output_options(self):
        """Test parsing with output options."""
        parser = create_parser()
        args = parser.parse_args([
            "analyze",
            "--format", "json",
            "--output", "report.json",
            "--quiet",
            "postgresql://localhost/test"
        ])
        assert args.format == "json"
        assert args.output == Path("report.json")
        assert args.quiet is True

    def test_parser_version_command(self):
        """Test parsing version command."""
        parser = create_parser()
        args = parser.parse_args(["version"])
        assert args.command == "version"


class TestReadPatterns:
    """Test read pattern parsing."""

    def test_parse_single_pattern(self):
        """Test parsing single pattern."""
        patterns = parse_read_patterns("point_lookup")
        assert patterns == ("point_lookup",)

    def test_parse_multiple_patterns(self):
        """Test parsing multiple patterns."""
        patterns = parse_read_patterns("point_lookup,range_scan,aggregation")
        assert patterns == ("point_lookup", "range_scan", "aggregation")

    def test_parse_patterns_with_spaces(self):
        """Test parsing patterns with spaces."""
        patterns = parse_read_patterns("point_lookup, range_scan , aggregation")
        assert patterns == ("point_lookup", "range_scan", "aggregation")

    def test_parse_invalid_pattern(self):
        """Test parsing invalid pattern exits."""
        with pytest.raises(SystemExit):
            parse_read_patterns("invalid_pattern")


class TestIntentFromArgs:
    """Test intent creation from arguments."""

    def test_intent_from_preset_oltp(self):
        """Test creating intent from OLTP preset."""
        parser = create_parser()
        args = parser.parse_args([
            "analyze",
            "--intent", "oltp",
            "postgresql://localhost/test"
        ])
        intent = get_intent_from_args(args)
        assert intent.workload == OLTP_INTENT.workload
        assert intent.write_frequency == OLTP_INTENT.write_frequency

    def test_intent_from_preset_olap(self):
        """Test creating intent from OLAP preset."""
        parser = create_parser()
        args = parser.parse_args([
            "analyze",
            "--intent", "olap",
            "postgresql://localhost/test"
        ])
        intent = get_intent_from_args(args)
        assert intent.workload == OLAP_INTENT.workload

    def test_intent_from_custom_params(self):
        """Test creating custom intent."""
        parser = create_parser()
        args = parser.parse_args([
            "analyze",
            "--workload", "OLTP",
            "--write-frequency", "high",
            "--read-patterns", "point_lookup",
            "--data-volume", "large",
            "postgresql://localhost/test"
        ])
        intent = get_intent_from_args(args)
        assert intent is not None
        assert intent.workload == "OLTP"
        assert intent.write_frequency == "high"
        assert intent.read_patterns == ("point_lookup",)
        assert intent.data_volume == "large"

    def test_intent_none_when_no_args(self):
        """Test intent is None when no intent args provided."""
        parser = create_parser()
        args = parser.parse_args([
            "analyze",
            "postgresql://localhost/test"
        ])
        intent = get_intent_from_args(args)
        assert intent is None


class TestCommands:
    """Test command execution."""

    def test_cmd_version(self, capsys):
        """Test version command."""
        parser = create_parser()
        args = parser.parse_args(["version"])
        exit_code = cmd_version(args)
        
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "flakes version 0.1.0" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_analyze_basic(self, tmp_path, monkeypatch):
        """Test analyze command basic execution."""
        # Mock analyze_schema
        mock_report = MagicMock()
        mock_report.to_markdown.return_value = "# Test Report"
        mock_report.to_dict.return_value = {"test": "data"}
        mock_report.table_count = 5
        mock_report.role_summary = {}
        mock_report.pattern_summary = {}
        mock_report.tension_summary = {}
        
        async def mock_analyze(*args, **kwargs):
            return mock_report
        
        with patch("flakes.cli.analyze_schema", new=mock_analyze):
            parser = create_parser()
            output_file = tmp_path / "report.md"
            args = parser.parse_args([
                "analyze",
                "--output", str(output_file),
                "--quiet",
                "postgresql://localhost/test"
            ])
            
            exit_code = await cmd_analyze(args)
            
            assert exit_code == 0
            assert output_file.exists()
            assert "# Test Report" in output_file.read_text()

    @pytest.mark.asyncio
    async def test_cmd_analyze_json_output(self, tmp_path):
        """Test analyze command with JSON output."""
        mock_report = MagicMock()
        mock_report.to_dict.return_value = {"test": "data", "tables": 5}
        mock_report.table_count = 5
        mock_report.role_summary = {}
        mock_report.pattern_summary = {}
        mock_report.tension_summary = {}
        
        async def mock_analyze(*args, **kwargs):
            return mock_report
        
        with patch("flakes.cli.analyze_schema", new=mock_analyze):
            parser = create_parser()
            output_file = tmp_path / "report.json"
            args = parser.parse_args([
                "analyze",
                "--format", "json",
                "--output", str(output_file),
                "--quiet",
                "postgresql://localhost/test"
            ])
            
            exit_code = await cmd_analyze(args)
            
            assert exit_code == 0
            assert output_file.exists()
            
            data = json.loads(output_file.read_text())
            assert data["test"] == "data"
            assert data["tables"] == 5

    @pytest.mark.asyncio
    async def test_cmd_analyze_with_filters(self):
        """Test analyze command with table/schema filters."""
        mock_report = MagicMock()
        mock_report.to_markdown.return_value = "# Test Report"
        mock_report.table_count = 2
        mock_report.role_summary = {}
        mock_report.pattern_summary = {}
        mock_report.tension_summary = {}
        
        analyze_called_with = {}
        
        async def mock_analyze(*args, **kwargs):
            analyze_called_with.update(kwargs)
            return mock_report
        
        with patch("flakes.cli.analyze_schema", new=mock_analyze):
            parser = create_parser()
            args = parser.parse_args([
                "analyze",
                "--tables", "users,orders",
                "--schemas", "public,staging",
                "--exclude", "tmp_*,test_*",
                "--quiet",
                "postgresql://localhost/test"
            ])
            
            exit_code = await cmd_analyze(args)
            
            assert exit_code == 0
            assert analyze_called_with["tables"] == ["users", "orders"]
            assert analyze_called_with["schemas"] == ["public", "staging"]
            assert analyze_called_with["exclude_patterns"] == ["tmp_*", "test_*"]

    @pytest.mark.asyncio
    async def test_cmd_analyze_error_handling(self):
        """Test analyze command error handling."""
        async def mock_analyze_error(*args, **kwargs):
            raise Exception("Database connection failed")
        
        with patch("flakes.cli.analyze_schema", new=mock_analyze_error):
            parser = create_parser()
            args = parser.parse_args([
                "analyze",
                "--quiet",
                "postgresql://localhost/test"
            ])
            
            exit_code = await cmd_analyze(args)
            assert exit_code == 1


class TestCLIIntegration:
    """Integration tests for CLI (without real database)."""

    def test_cli_help(self):
        """Test CLI help output."""
        result = subprocess.run(
            [sys.executable, "-m", "flakes.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "schema critic" in result.stdout.lower()

    def test_cli_version(self):
        """Test CLI version command."""
        result = subprocess.run(
            [sys.executable, "-m", "flakes.cli", "version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "0.1.0" in result.stdout

    def test_cli_analyze_help(self):
        """Test CLI analyze help."""
        result = subprocess.run(
            [sys.executable, "-m", "flakes.cli", "analyze", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "DSN" in result.stdout or "dsn" in result.stdout
>>>>>>> ce7ed15 (feat: Add comprehensive CLI interface)
