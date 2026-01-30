"""Tests to fix specific coverage gaps."""

import sys
import importlib
from importlib import metadata
from unittest.mock import patch, MagicMock
import pytest
import builtins

def test_cli_version_fallback():
    """Test that CLI version falls back to 0.0.0-dev when package not found."""
    # Ensure module is not in cache
    if "flaqes.cli" in sys.modules:
        del sys.modules["flaqes.cli"]
    
    # We mock metadata.version just for the context of importing flaqes.cli
    with patch("importlib.metadata.version", side_effect=metadata.PackageNotFoundError):
        import flaqes.cli
        assert flaqes.cli.__version__ == "0.0.0-dev"
    
    # Restore normal module
    if "flaqes.cli" in sys.modules:
        del sys.modules["flaqes.cli"]
    import flaqes.cli


def test_snapshot_engine_import_error():
    """Test SnapshotEngine module level import error handling."""
    # Remove from sys.modules to force reload
    if "flaqes.evolution.snapshot" in sys.modules:
        del sys.modules["flaqes.evolution.snapshot"]
    
    # Mechanism to raise ImportError for 'alembic'
    real_import = builtins.__import__
    
    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "alembic" or (fromlist and "alembic" in name):
            raise ImportError("No alembic")
        return real_import(name, globals, locals, fromlist, level)
    
    with patch("builtins.__import__", side_effect=mock_import):
        # We need to ensure we don't pick up cached alembic modules
        with patch.dict(sys.modules):
            # Remove any alembic entries from the mocked sys.modules
            for k in list(sys.modules.keys()):
                if "alembic" in k:
                    del sys.modules[k]
            
            import flaqes.evolution.snapshot
            assert flaqes.evolution.snapshot.ALEMBIC_AVAILABLE is False
            assert flaqes.evolution.snapshot.Config is None
            assert flaqes.evolution.snapshot.command is None

    # Restore module
    if "flaqes.evolution.snapshot" in sys.modules:
        del sys.modules["flaqes.evolution.snapshot"]
    import flaqes.evolution.snapshot


def test_snapshot_init_raises_if_no_alembic():
    """Test that SnapshotEngine raises ImportError if alembic is not available."""
    from flaqes.evolution import snapshot
    
    # Save original state
    original_flag = snapshot.ALEMBIC_AVAILABLE
    
    try:
        snapshot.ALEMBIC_AVAILABLE = False
        with pytest.raises(ImportError, match="Alembic is required"):
            snapshot.SnapshotEngine()
    finally:
        snapshot.ALEMBIC_AVAILABLE = original_flag
