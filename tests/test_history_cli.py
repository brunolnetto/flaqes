"""Tests for the history CLI command."""

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flaqes.cli import run_history, create_parser

class TestHistoryCLI:
    """Tests for the history command."""
    
    def test_history_parser_no_orphans(self):
        """Test argument parsing."""
        parser = create_parser()
        args = parser.parse_args(["history", "--no-orphans", "--output", "file.mmd"])
        assert args.command == "history"
        assert args.show_orphans is False
        assert args.output == "file.mmd"

    @patch("barmaid.cli.parse_migration_file")
    @patch("barmaid.cli.generate_mermaid_diagram")
    @patch("pathlib.Path")
    def test_run_history_success(self, mock_path_cls, mock_gen, mock_parse, capsys):
        """Test successful history generation."""
        # Mock Path structure
        mock_dir = MagicMock()
        mock_file = MagicMock()
        mock_file.name = "123_rev.py"
        
        # When Path(arg) is called
        mock_instance = MagicMock()
        mock_instance.exists.return_value = True
        mock_instance.is_dir.return_value = True
        # glob returns files
        mock_instance.glob.return_value = [mock_file]
        
        # Setup Path return value
        # Note: patch('pathlib.Path') mocks the class. 
        # Making sure Path(...) returns our mock instance.
        mock_path_cls.return_value = mock_instance
        
        # Also need to handle iterating over search paths if not provided
        # But here path="versions" is provided, so it calls Path("versions")
        
        mock_parse.return_value = {"revision": "123", "down_revision": None}
        mock_gen.return_value = "graph TD;"
        
        args = argparse.Namespace(
            path="versions",
            direction="TD",
            show_orphans=True,
            output=None,
            wrap=False
        )
        
        ret = run_history(args)
        assert ret == 0
        
        captured = capsys.readouterr()
        assert "graph TD;" in captured.out

    @patch("barmaid.cli.parse_migration_file")
    @patch("barmaid.cli.generate_mermaid_diagram")
    @patch("pathlib.Path")
    def test_run_history_output_file(self, mock_path_cls, mock_gen, mock_parse, capsys, tmp_path):
        """Test history generation writing to file."""
        mock_instance = MagicMock()
        mock_instance.exists.return_value = True
        mock_instance.is_dir.return_value = True
        mock_file = MagicMock()
        mock_file.name = "123.py"
        mock_instance.glob.return_value = [mock_file]
        mock_path_cls.return_value = mock_instance
        
        mock_parse.return_value = {"revision": "123"}
        mock_gen.return_value = "graph TD;"
        
        output_file = tmp_path / "graph.mmd"
        
        args = argparse.Namespace(
            path="versions",
            direction="TD",
            show_orphans=True,
            output=str(output_file),
            wrap=False
        )
        
        ret = run_history(args)
        assert ret == 0
        
        assert output_file.read_text() == "graph TD;"
        
        captured = capsys.readouterr()
        assert "History diagram saved to" in captured.err

    @patch("pathlib.Path")
    def test_run_history_no_migrations(self, mock_path_cls, capsys):
        """Test when no migrations found."""
        mock_instance = MagicMock()
        mock_instance.exists.return_value = True
        mock_instance.is_dir.return_value = True
        mock_instance.glob.return_value = [] # Empty
        mock_path_cls.return_value = mock_instance
        
        args = argparse.Namespace(path="versions")
        ret = run_history(args)
        assert ret == 1
        
        captured = capsys.readouterr()
        assert "No migrations found" in captured.err

    def test_run_history_barmaid_import_error(self, capsys):
        """Test missing barmaid."""
        with patch.dict(sys.modules, {"barmaid.cli": None}):
            if "barmaid.cli" in sys.modules:
                del sys.modules["barmaid.cli"]
            pass 
            
    @patch("pathlib.Path")
    def test_run_history_no_dir(self, mock_path_cls, capsys):
        """Test failure to find versions directory."""
        mock_instance = MagicMock()
        mock_instance.exists.return_value = False # Not found
        mock_path_cls.return_value = mock_instance
        
        args = argparse.Namespace(path=None)
        ret = run_history(args)
        assert ret == 1
        
        captured = capsys.readouterr()
        assert "Error: Could not find versions directory" in captured.err

