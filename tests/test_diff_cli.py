"""Tests for the diff command."""

import argparse
from unittest.mock import MagicMock, patch

import pytest
from flaqes.evolution import DiffEngine, SchemaDelta
from flaqes.core.schema_graph import SchemaGraph, Table, Column, DataType
from flaqes.core.types import DataTypeCategory
from flaqes.cli import run_diff, create_parser

def make_table(name: str, col_names: list[str]) -> Table:
    """Helper to create a simple table."""
    cols = [
        Column(
            name=c, 
            data_type=DataType("integer", DataTypeCategory.INTEGER)
        ) for c in col_names
    ]
    return Table(name=name, columns=cols)


class TestSnapshotEngineInternals:
    """Tests for internal SnapshotEngine logic."""

    @patch("flaqes.evolution.snapshot.ALEMBIC_AVAILABLE", True)
    @patch("flaqes.evolution.snapshot.Path")
    def test_init_ini_search(self, mock_path):
        """Test searching for alembic.ini in cwd."""
        
        # Scenario: Absolute path doesn't exist, relative path logic triggers
        provided_path = "subdir/alembic.ini"
        
        # mock_path(provided_path) -> mock object
        mock_ini = MagicMock()
        mock_path.return_value = mock_ini
        
        # 1. First check: provided path exists? -> False
        mock_ini.exists.side_effect = [False, True, True] 
        # sequence: 
        # 1. self.ini_path.exists() -> False
        # 2. cwd_path.exists() -> True (inside fallback block)
        # 3. Final self.ini_path.exists() check -> True
        
        mock_ini.is_absolute.return_value = False
        
        # Mock Path.cwd() / ... logic
        mock_cwd = MagicMock()
        mock_path.cwd.return_value = mock_cwd
        mock_cwd.__truediv__.return_value = mock_ini # Join returns same mock for simplicity or a new one
        # If we return same "mock_ini", the side_effect on exists() handles the transitions.
        
        from flaqes.evolution.snapshot import SnapshotEngine
        engine = SnapshotEngine(provided_path)
        
        assert engine.ini_path == mock_ini


class TestDiffEngine:
    """Tests for the DiffEngine logic."""
    
    def test_structural_changes(self):
        """Test detection of added/removed/modified tables."""
        engine = DiffEngine()
        
        # Base: users, orders
        base = SchemaGraph()
        base.add_table(make_table("users", ["id", "name"]))
        base.add_table(make_table("orders", ["id", "user_id"]))
        
        # Head: users (mod), products (new), orders (removed)
        head = SchemaGraph()
        # users has new column
        head.add_table(make_table("users", ["id", "name", "email"]))
        # products is new
        head.add_table(make_table("products", ["id", "price"]))
        
        delta = engine.compute(base, head)
        
        assert delta.added_tables == ["public.products"]
        assert delta.removed_tables == ["public.orders"]
        assert delta.modified_tables == ["public.users"]
        assert delta.has_changes() is True

    def test_no_changes(self):
        """Test identical graphs."""
        engine = DiffEngine()
        base = SchemaGraph()
        base.add_table(make_table("t1", ["c1"]))
        
        delta = engine.compute(base, base)
        assert not delta.has_changes()

    def test_semantic_role_drift(self):
        """Test detection of role changes."""
        from flaqes.core.types import DataTypeCategory
        engine = DiffEngine()
        
        # Base: users as typical Dimension (has text columns, no FKs)
        base = SchemaGraph()
        cols = [
            Column("id", DataType("int", DataTypeCategory.INTEGER)),
            Column("name", DataType("text", DataTypeCategory.TEXT)),
            Column("email", DataType("text", DataTypeCategory.TEXT)),
            Column("status", DataType("text", DataTypeCategory.TEXT)), 
        ]
        t1 = Table("users", columns=cols)
        # Mock surrogate key logic or just rely on signals
        # For simplicity, we trust the RoleDetector logic, but we can't easily mock
        # RoleDetector inside the engine without dependency injection or patching.
        # So we construct a table that will definitively look like a Dimension.
        base.add_table(t1)
        
        # Head: users evolved into a Fact table (many numeric columns, looks like transactions)
        head = SchemaGraph()
        cols_fact = [
            Column("id", DataType("int", DataTypeCategory.INTEGER)),
            Column("amount", DataType("int", DataTypeCategory.INTEGER)),
            Column("qty", DataType("int", DataTypeCategory.INTEGER)),
            Column("user_id", DataType("int", DataTypeCategory.INTEGER)), # FK-like
            Column("created_at", DataType("timestamp", DataTypeCategory.TIMESTAMP)),
        ]
        t2 = Table("users", columns=cols_fact) 
        # Add FKs to make it look like a fact table
        # We need mock FKs
        head.add_table(t2)
        
        # We need to ensure RoleDetector sees different roles.
        # Since RoleDetector logic is complex, it's safer to Mock it in this test 
        # to ensure we test DiffEngine, not RoleDetector.
        
        with patch("flaqes.analysis.role_detector.RoleDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector_cls.return_value = mock_detector
            
            # Setup mock returns
            from flaqes.analysis.role_detector import TableRoleResult
            from flaqes.core.types import RoleType
            
            # Base -> DIMENSION
            res1 = TableRoleResult("users", RoleType.DIMENSION, 0.8)
            # Head -> FACT
            res2 = TableRoleResult("users", RoleType.FACT, 0.9)
            
            mock_detector.detect.side_effect = [res1, res2]
            
            delta = engine.compute(base, head)
            
            assert len(delta.role_drifts) == 1
            drift = delta.role_drifts[0]
            assert drift.table_name == "public.users"
            assert drift.old_role == RoleType.DIMENSION
            assert drift.new_role == RoleType.FACT

    def test_diff_edge_cases(self):
        """Test edge cases in diff comparison."""
        engine = DiffEngine()
        
        # Test 1: PK Mismatch
        t1 = make_table("users", ["id"])
        # Manually set PKs to be different
        object.__setattr__(t1, "primary_key", MagicMock(columns=("id",)))
        
        t2 = make_table("users", ["id"]) 
        object.__setattr__(t2, "primary_key", MagicMock(columns=("other_id",)))
        
        assert engine._is_modified(t1, t2) is True
        
        # Test 2: None handling (should return True for modified if one is None, 
        # though effectively this path isn't reached by compute() logic for common tables)
        assert engine._is_modified(None, t2) is True
        assert engine._is_modified(t1, None) is True

        assert engine._is_modified(None, t2) is True
        assert engine._is_modified(t1, None) is True
        
    def test_is_modified_columns(self):
        """Test specific column modification cases."""
        engine = DiffEngine()
        t1 = make_table("users", ["id", "name"])
        
        # Case 1: Same columns, different types
        cols_mod = [
             Column("id", DataType("integer", DataTypeCategory.INTEGER)),
             Column("name", DataType("varchar", DataTypeCategory.TEXT)) # changed from text default in helper?
        ]
        # Helper uses "integer" for logic, let's just manually construct
        t2 = Table("users", columns=[
            Column("id", DataType("integer", DataTypeCategory.INTEGER)),
            Column("name", DataType("text", DataTypeCategory.TEXT)) # Changed type
        ])
        assert engine._is_modified(t1, t2) is True
        
        # Case 2: Different PK
        t3 = make_table("users", ["id", "name"])
        # t3 PK is 'id' by default helper ??? No helper doesn't set PK?
        # Helper: return Table(name=name, columns=cols) -> Table defaults pk to None?
        # Let's check Table definition. If defaults None, then pk1 != pk2 check needs one to have PK.
        
        t3.primary_key = MagicMock(columns=("id",))
        t4 = make_table("users", ["id", "name"])
        t4.primary_key = None
        
        assert engine._is_modified(t3, t4) is True

    def test_role_drift_description(self):
        """Test RoleDrift string representation."""
        from flaqes.evolution.diff import RoleDrift
        from flaqes.core.types import RoleType
        
        drift = RoleDrift(
            table_name="users",
            old_role=RoleType.ENTITY,
            new_role=RoleType.DIMENSION,
            confidence_delta=0.5
        )
        assert "Role changed from ENTITY to DIMENSION" in drift.description
        assert "(confidence +50%)" in drift.description
        
        drift_neg = RoleDrift(
            table_name="users",
            old_role=RoleType.DIMENSION,
            new_role=RoleType.ENTITY,
            confidence_delta=-0.2
        )
        assert "(confidence -20%)" in drift_neg.description


class TestDiffCLI:
    """Tests for the diff CLI command."""
    
    def test_parser(self):
        parser = create_parser()
        args = parser.parse_args(["diff", "base", "head"])
        assert args.command == "diff"
        assert args.base_rev == "base"
        assert args.head_rev == "head"

    @patch("flaqes.evolution.SnapshotEngine")
    def test_success_text(self, mock_engine_cls, capsys):
        """Test successful diff execution with text output."""
        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine
        
        # Mock graphs
        mock_engine.get_schema_at_revision.side_effect = [
            SchemaGraph(), # base (empty)
            SchemaGraph.from_tables([make_table("new_table", ["id"])]) # head
        ]
        
        args = argparse.Namespace(
            base_rev="base",
            head_rev="head",
            config="alembic.ini",
            format="text"
        )
        
        result = run_diff(args)
        assert result == 0
        
        captured = capsys.readouterr()
        assert "# Schema Diff: base -> head" in captured.out
        assert "+ public.new_table" in captured.out
