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
