"""Tests for the evolution command."""

import argparse
from unittest.mock import MagicMock, patch

import pytest
from flaqes.core.schema_graph import SchemaGraph
from flaqes.evolution import EvolutionReportEngine, EvolutionStep, SchemaDelta
from flaqes.visualization import sparkline, format_trend
from flaqes.cli import run_evolution, create_parser

class TestVisualization:
    """Tests for visualization helpers."""
    
    def test_sparkline(self):
        assert sparkline([1, 2, 3]) == " ▄█"
        assert sparkline([1, 1, 1]) == "▅▅▅"
        assert sparkline([]) == ""
        
    def test_trend(self):
        assert format_trend(10, 8) == "10 (↑ 2)"
        assert format_trend(5, 8) == "5 (↓ 3)"
        assert format_trend(5, 5) == "5 (-)"


class TestEvolutionReportEngine:
    """Tests for the report engine logic."""
    
    def test_analyze_range(self):
        mock_snapshot_engine = MagicMock()
        mock_snapshot_engine.get_schema_at_revision.side_effect = [
            SchemaGraph(), # rev1
            SchemaGraph()  # rev2
        ]
        
        engine = EvolutionReportEngine(mock_snapshot_engine)
        
        revisions = ["rev1", "rev2"]
        steps = list(engine.analyze_range(revisions))
        
        assert len(steps) == 2
        assert steps[0].revision_id == "rev1"
        assert steps[0].message == "Start of range"
        
        assert steps[1].revision_id == "rev2"
        # Delta should be verified (assuming DiffEngine works)
        assert isinstance(steps[1].delta, SchemaDelta)


class TestEvolutionCLI:
    """Tests for the evolution CLI command."""
    
    def test_parser(self):
        parser = create_parser()
        args = parser.parse_args(["evolution", "--limit", "20"])
        assert args.command == "evolution"
        assert args.limit == 20

    @patch("flaqes.evolution.SnapshotEngine")
    @patch("pathlib.Path") # Patch global Path since it's imported inside function
    @patch("barmaid.cli.parse_migration_file")
    def test_success(self, mock_parse_mig, mock_path_cls, mock_engine_cls, capsys):
        """Test successful evolution report generation."""
        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine
        
        # Mock file discovery
        mock_dir = MagicMock()
        mock_file1 = MagicMock()
        mock_file2 = MagicMock()
        
        # Setup Path("alembic/versions").exists() -> True
        # When Path(...) is called, it returns a mock instance.
        # We need to make sure one of the probed paths returns a mock that has .exists() = True
        
        # Logic in CLI:
        # for p in [Path("alembic/versions"), ...]:
        #   if p.exists(): ...
        
        # We start with mock_path_cls (the class). 
        # Calling mock_path_cls("string") returns a NEW mock instance each time unless side_effect configured.
        
        mock_instance = MagicMock()
        mock_path_cls.return_value = mock_instance
        mock_instance.exists.return_value = True
        mock_instance.glob.return_value = [mock_file1]
        
        mock_parse_mig.side_effect = [
            {'revision': 'rev1'}
        ]
        
        # Mock schema retrieval for 1 revision
        mock_engine.get_schema_at_revision.side_effect = [
            SchemaGraph(), # rev1
        ]

        # We need to ensure we trick the logic that checks for versions_dir.exists()
        # mock_path("...").exists() -> True
        mock_dir.exists.return_value = True
        
        args = argparse.Namespace(
            history_path="versions",
            limit=10,
            config="alembic.ini"
        )
        
        result = run_evolution(args)
        
        captured = capsys.readouterr()
        if result != 0:
            print(f"CLI Error Output: {captured.err}")
            
        assert result == 0
        
        assert "# Evolution Report (1 revisions)" in captured.out
        assert "| `rev1` |" in captured.out

    @patch("flaqes.evolution.SnapshotEngine")
    def test_no_barmaid(self, mock_engine_cls, capsys):
        """Test handling when barmaid is missing."""
        
        args = argparse.Namespace(
            history_path=None, 
            limit=10,
            config="alembic.ini"
        )
        
        # Patch pathlib.Path to simulate no directories existing
        with patch("pathlib.Path") as mock_path_cls:
             mock_path_cls.return_value.exists.return_value = False
             
             result = run_evolution(args)
             assert result == 1
             
             captured = capsys.readouterr()
             assert "Error: No revisions found" in captured.err
