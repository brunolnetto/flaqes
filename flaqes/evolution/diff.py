"""
Differential analysis for schema evolution.

This module provides tools to compare two SchemaGraph objects and detect
both structural changes (tables added/removed) and semantic drifts (role changes,
new tensions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from flaqes.core.types import RoleType

if TYPE_CHECKING:
    from flaqes.core.schema_graph import SchemaGraph, Table


@dataclass
class RoleDrift:
    """Represents a change in the detected role of a table."""
    table_name: str
    old_role: RoleType
    new_role: RoleType
    confidence_delta: float
    
    @property
    def description(self) -> str:
        sign = "+" if self.confidence_delta > 0 else ""
        return (
            f"Role changed from {self.old_role.name} to {self.new_role.name} "
            f"(confidence {sign}{self.confidence_delta:.0%})"
        )


@dataclass
class SchemaDelta:
    """
    Represents the difference between two schema states.
    """
    source_rev: str
    target_rev: str
    
    # Structural Changes
    added_tables: list[str] = field(default_factory=list)
    removed_tables: list[str] = field(default_factory=list)
    modified_tables: list[str] = field(default_factory=list)
    
    # Semantic Changes (populated by high-level analysis)
    role_drifts: list[RoleDrift] = field(default_factory=list)
    
    def has_changes(self) -> bool:
        return bool(
            self.added_tables or 
            self.removed_tables or 
            self.modified_tables or
            self.role_drifts
        )


class DiffEngine:
    """Computes differences between schema graphs."""
    
    def compute(self, base: SchemaGraph, head: SchemaGraph, base_rev: str = "base", head_rev: str = "head") -> SchemaDelta:
        """
        Compute the delta between two schema graphs.
        
        Args:
            base: The starting state.
            head: The target state.
            base_rev: Label for the base revision.
            head_rev: Label for the head revision.
            
        Returns:
            SchemaDelta object.
        """
        delta = SchemaDelta(source_rev=base_rev, target_rev=head_rev)
        
        base_tables = set(base.tables.keys())
        head_tables = set(head.tables.keys())
        
        # Structural structural analysis
        delta.added_tables = sorted(list(head_tables - base_tables))
        delta.removed_tables = sorted(list(base_tables - head_tables))
        
        # Semantic structural analysis
        from flaqes.analysis.role_detector import RoleDetector
        detector = RoleDetector()
        
        common_tables = base_tables.intersection(head_tables)
        for fqn in common_tables:
            table_base = base.get_table(fqn)
            table_head = head.get_table(fqn)
            
            # Structural modifications
            if self._is_modified(table_base, table_head):
                delta.modified_tables.append(fqn)
                
            # Semantic Role Drift
            role_base = detector.detect(table_base, base)
            role_head = detector.detect(table_head, head)
            
            if role_base.primary_role != role_head.primary_role:
                from flaqes.evolution.diff import RoleDrift
                delta.role_drifts.append(RoleDrift(
                    table_name=fqn,
                    old_role=role_base.primary_role,
                    new_role=role_head.primary_role,
                    confidence_delta=role_head.confidence - role_base.confidence
                ))
                
        return delta

    def _is_modified(self, t1: Table, t2: Table) -> bool:
        """Check if a table has structural modifications."""
        if t1 is None or t2 is None:
            return True
            
        # Check columns (naive comparison)
        if len(t1.columns) != len(t2.columns):
            return True
            
        t1_cols = {c.name: c.data_type.raw for c in t1.columns}
        t2_cols = {c.name: c.data_type.raw for c in t2.columns}
        if t1_cols != t2_cols:
            return True
            
        # Check PK
        pk1 = tuple(t1.primary_key.columns) if t1.primary_key else ()
        pk2 = tuple(t2.primary_key.columns) if t2.primary_key else ()
        if pk1 != pk2:
            return True
            
        return False
