"""
Wayback Machine / Snapshot Engine.

This module is responsible for reconstructing the database schema at a specific
point in history by using Alembic's offline SQL generation capabilities.
"""

from __future__ import annotations

import io
import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flaqes.core.schema_graph import SchemaGraph

# Try to import alembic, but don't fail hard if it's not installed
# since evolution features are optional dependencies
try:
    from alembic.config import Config
    from alembic import command
    ALEMBIC_AVAILABLE = True
except ImportError:
    ALEMBIC_AVAILABLE = False
    Config = None
    command = None


class SnapshotError(Exception):
    """Raised when snapshot generation fails."""
    pass


class SnapshotEngine:
    """
    Reconstructs schema state at arbitrary revisions.
    
    This works by:
    1. Configuring Alembic programmatically
    2. Running `upgrade <rev> --sql` to generate the DDL
    3. Parsing the logic with flaqes' DDL parser
    """
    
    def __init__(self, alembic_ini_path: str | Path = "alembic.ini"):
        if not ALEMBIC_AVAILABLE:
            raise ImportError(
                "Alembic is required for evolution features. "
                "Install it with 'pip install alembic'."
            )
        
        self.ini_path = Path(alembic_ini_path)
        if not self.ini_path.exists():
             # Fallback: look in current directory if not absolute
             if not self.ini_path.is_absolute():
                 cwd_path = Path.cwd() / alembic_ini_path
                 if cwd_path.exists():
                     self.ini_path = cwd_path

        if not self.ini_path.exists():
            raise SnapshotError(f"Alembic config file not found: {self.ini_path}")
            
    def get_schema_at_revision(self, revision: str) -> SchemaGraph:
        """
        Get the schema graph as it existed at the given revision.
        
        Args:
            revision: The revision ID (e.g., 'head', 'base', '1a2b3c')
            
        Returns:
            SchemaGraph object representing that state.
        """
        from flaqes.introspection.ddl_parser import parse_ddl
        
        # 1. Generate SQL via Alembic
        sql = self._generate_sql(revision)
        
        # 2. Parse DDL into SchemaGraph
        try:
            graph = parse_ddl(sql)
            return graph
        except Exception as e:
            raise SnapshotError(f"Failed to parse generated DDL for revision {revision}: {e}")

    def _generate_sql(self, revision: str) -> str:
        """Run alembic upgrade --sql to get the DDL."""
        # Capture stdout to get the SQL
        buffer = io.StringIO()
        
        # Setup Alembic Config
        # We need to ensure we don't actually connect to a DB, but Alembic needs
        # a url in the config usually.
        config = Config(str(self.ini_path))
        
        # Force offline mode attributes if needed, though 'upgrade --sql' usually implies it.
        # However, we must ensure the script location is correct relative to the ini.
        
        try:
            with contextlib.redirect_stdout(buffer):
                # Upgrade from base (start) to the target revision
                # This replays ALL migration history up to that point
                command.upgrade(config, f"{revision}", sql=True)
                
            return buffer.getvalue()
        except Exception as e:
            raise SnapshotError(f"Alembic upgrade failed: {e}")
