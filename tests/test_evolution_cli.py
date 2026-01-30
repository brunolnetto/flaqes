"""Tests for the analyze-rev command."""

import argparse
import sys
from unittest.mock import MagicMock, patch

import pytest
from flaqes.evolution import SnapshotError
# We don't import SnapshotEngine directly to avoid the ImportError if alembic is missing
from flaqes.cli import run_analyze_rev, create_parser


class TestAnalyzeRev:
    """Tests for the analyze-rev command."""

    def test_parser(self):
        """Test analyze-rev argument parsing."""
        parser = create_parser()
        args = parser.parse_args(["analyze-rev", "head", "--workload", "OLTP"])
        assert args.command == "analyze-rev"
        assert args.revision == "head"
        assert args.workload == "OLTP"
        assert args.config == "alembic.ini"

    @patch("flaqes.evolution.snapshot.ALEMBIC_AVAILABLE", True)
    @patch("flaqes.evolution.SnapshotEngine")
    def test_success(self, mock_engine_cls, capsys):
        """Test successful execution."""
        # Mock engine instance
        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine
        
        # Mock schema graph
        mock_graph = MagicMock()
        mock_engine.get_schema_at_revision.return_value = mock_graph
        
        # Patch generate_report where it is imported from
        with patch("flaqes.generate_report") as mock_report_gen:
            mock_report = MagicMock()
            mock_report.to_markdown.return_value = "# Report"
            mock_report_gen.return_value = mock_report
            
            args = argparse.Namespace(
                revision="head",
                config="alembic.ini",
                workload="mixed",
                volume="medium",
                format="markdown"
            )
            
            result = run_analyze_rev(args)
            
            captured = capsys.readouterr()
            assert result == 0
            
            assert "# Analysis for Revision: head" in captured.out
            assert "# Report" in captured.out

    @patch("flaqes.evolution.snapshot.ALEMBIC_AVAILABLE", True)
    @patch("flaqes.evolution.SnapshotEngine")
    def test_snapshot_error(self, mock_engine_cls, capsys):
        """Test handling of snapshot errors."""
        # The mock needs to raise when instantiated
        mock_engine_cls.side_effect = SnapshotError("Config not found")
        
        args = argparse.Namespace(
            revision="head",
            config="missing.ini",
            workload="mixed",
            volume="medium"
        )
        
        result = run_analyze_rev(args)
        assert result == 1
        
        captured = capsys.readouterr()
        assert "Error: Snapshot generation failed" in captured.err

    @patch("flaqes.evolution.snapshot.ALEMBIC_AVAILABLE", True)
    @patch("flaqes.evolution.SnapshotEngine")
    def test_import_error(self, mock_engine_cls, capsys):
        """Test handling of missing dependencies."""
        mock_engine_cls.side_effect = ImportError("Alembic missing")
        
        args = argparse.Namespace(
            revision="head",
            config="alembic.ini",
            workload="mixed",
            volume="medium"
        )
        
        result = run_analyze_rev(args)
        assert result == 1
        
        captured = capsys.readouterr()
        assert "Error: Alembic missing" in captured.err


class TestSnapshotEngine:
    """Tests for the SnapshotEngine class."""
    
    @patch("flaqes.evolution.snapshot.ALEMBIC_AVAILABLE", True)
    def test_init_missing_config(self):
        """Test init with missing config file."""
        from flaqes.evolution.snapshot import SnapshotEngine, SnapshotError
        with pytest.raises(SnapshotError, match="Alembic config file not found"):
             # Use a definitely non-existent path
            SnapshotEngine("nonexistent_alembic.ini")

    @patch("flaqes.evolution.snapshot.ALEMBIC_AVAILABLE", False)
    def test_init_missing_alembic(self):
        """Test init when alembic is not installed."""
        from flaqes.evolution.snapshot import SnapshotEngine
        with pytest.raises(ImportError, match="Alembic is required"):
            SnapshotEngine()


class TestSnapshotEngineInternals:
    """Tests for the internal logic of SnapshotEngine (mocking alembic lib)."""
    
    @patch("flaqes.evolution.snapshot.ALEMBIC_AVAILABLE", True)
    @patch("flaqes.evolution.snapshot.Config")
    @patch("flaqes.evolution.snapshot.command")
    def test_generate_sql(self, mock_command, mock_config, tmp_path):
        """Test the _generate_sql method calls alembic correctly."""
        from flaqes.evolution.snapshot import SnapshotEngine
        
        # Create a dummy alembic.ini
        ini_file = tmp_path / "alembic.ini"
        ini_file.touch()
        
        engine = SnapshotEngine(str(ini_file))
        
        # Determine what the command prints to stdout
        def side_effect(config, revision, sql):
            print("CREATE TABLE foo (id INT);")
            
        mock_command.upgrade.side_effect = side_effect
        
        sql = engine._generate_sql("head")
        
        assert "CREATE TABLE foo" in sql
        mock_command.upgrade.assert_called_once()
        args, kwargs = mock_command.upgrade.call_args
        assert kwargs["sql"] is True
        assert args[1] == "head"

    @patch("flaqes.evolution.snapshot.ALEMBIC_AVAILABLE", True)
    @patch("flaqes.evolution.snapshot.Config")
    @patch("flaqes.evolution.snapshot.command")
    def test_generate_sql_error(self, mock_command, mock_config, tmp_path):
        """Test handling of alembic errors."""
        from flaqes.evolution.snapshot import SnapshotEngine, SnapshotError
        
        ini_file = tmp_path / "alembic.ini"
        ini_file.touch()
        engine = SnapshotEngine(str(ini_file))
        
        mock_command.upgrade.side_effect = Exception("Alembic error")
        
        with pytest.raises(SnapshotError, match="Alembic upgrade failed"):
            engine._generate_sql("head")

    @patch("flaqes.evolution.snapshot.ALEMBIC_AVAILABLE", True)
    @patch("flaqes.evolution.snapshot.Config")
    @patch("flaqes.evolution.snapshot.command")
    @patch("flaqes.introspection.ddl_parser.parse_ddl")
    def test_get_schema_at_revision(self, mock_parse, mock_command, mock_config, tmp_path):
        """Test the full flow of get_schema_at_revision."""
        from flaqes.evolution.snapshot import SnapshotEngine
        
        ini_file = tmp_path / "alembic.ini"
        ini_file.touch()
        engine = SnapshotEngine(str(ini_file))
        
        mock_command.upgrade.side_effect = lambda *args, **kwargs: print("SQL")
        mock_parse.return_value = "MockGraph"
        
        graph = engine.get_schema_at_revision("head")
        
        assert graph == "MockGraph"
        mock_parse.assert_called_with("SQL\n")

    @patch("flaqes.evolution.snapshot.ALEMBIC_AVAILABLE", True)
    @patch("flaqes.evolution.snapshot.Config")
    @patch("flaqes.evolution.snapshot.command")
    @patch("flaqes.introspection.ddl_parser.parse_ddl")
    def test_get_schema_at_revision_parse_error(self, mock_parse, mock_command, mock_config, tmp_path):
        """Test handling of DDL parsing errors."""
        from flaqes.evolution.snapshot import SnapshotEngine, SnapshotError
        
        ini_file = tmp_path / "alembic.ini"
        ini_file.touch()
        engine = SnapshotEngine(str(ini_file))
        
        # SQL generation succeeds
        mock_command.upgrade.side_effect = lambda *args, **kwargs: print("BAD SQL")
        
        # Parse fails
        mock_parse.side_effect = Exception("Parse error")
        
        with pytest.raises(SnapshotError, match="Failed to parse generated DDL"):
            engine.get_schema_at_revision("head")
