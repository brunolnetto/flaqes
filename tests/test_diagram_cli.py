"""Tests for the diagram CLI command."""

import tempfile

import pytest

from flaqes.cli import main


class TestDiagramCLI:
    """Test cases for the diagram command."""

    def test_diagram_from_ddl_file(self, capsys) -> None:
        """Test generating diagram from DDL file."""
        from unittest.mock import patch
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("""
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                name TEXT
            );
            
            CREATE TABLE posts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                title TEXT NOT NULL
            );
            """)
            f.flush()
            
            with patch("sys.argv", ["flaqes", "diagram", "--ddl", f.name]):
                result = main()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "erDiagram" in captured.out
        assert "users {" in captured.out
        assert "posts {" in captured.out

    def test_diagram_with_wrap(self, capsys) -> None:
        """Test generating diagram with markdown wrap."""
        from unittest.mock import patch
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("CREATE TABLE simple (id SERIAL PRIMARY KEY);")
            f.flush()
            
            with patch("sys.argv", ["flaqes", "diagram", "--ddl", f.name, "--wrap"]):
                result = main()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "```mermaid" in captured.out
        assert "```" in captured.out

    def test_diagram_no_columns(self, capsys) -> None:
        """Test generating diagram without columns."""
        from unittest.mock import patch
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("CREATE TABLE simple (id SERIAL PRIMARY KEY, name TEXT);")
            f.flush()
            
            with patch("sys.argv", ["flaqes", "diagram", "--ddl", f.name, "--no-columns"]):
                result = main()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "erDiagram" in captured.out
        assert "{" not in captured.out

    def test_diagram_requires_dsn_or_ddl(self, capsys) -> None:
        """Test that diagram requires either --dsn or --ddl."""
        from unittest.mock import patch
        
        with patch("sys.argv", ["flaqes", "diagram"]):
            result = main()
        
        assert result == 1
        captured = capsys.readouterr()
        assert "Either --dsn or --ddl is required" in captured.err

    def test_diagram_rejects_both_dsn_and_ddl(self, capsys) -> None:
        """Test that diagram rejects both --dsn and --ddl."""
        from unittest.mock import patch
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("CREATE TABLE t (id INT);")
            f.flush()
            
            with patch("sys.argv", ["flaqes", "diagram", "--dsn", "postgresql://x", "--ddl", f.name]):
                result = main()
        
        assert result == 1
        captured = capsys.readouterr()
        assert "Cannot use both --dsn and --ddl" in captured.err
