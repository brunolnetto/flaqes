"""
Evolution Report Engine.

Generates a summary of schema evolution over a range of revisions.
"""

from typing import Iterable
from dataclasses import dataclass
from flaqes.core.schema_graph import SchemaGraph
from flaqes.evolution.diff import DiffEngine, SchemaDelta

@dataclass
class EvolutionStep:
    revision_id: str
    message: str
    delta: SchemaDelta
    table_count: int
    tension_count: int = 0  # Placeholder for Phase 4

class EvolutionReportEngine:
    """Analyze a sequence of revisions."""
    
    def __init__(self, snapshot_engine):
        self.snapshot_engine = snapshot_engine
        self.diff_engine = DiffEngine()
        
    def analyze_range(self, revisions: list[str]) -> Iterable[EvolutionStep]:
        """
        Analyze a sequence of revisions.
        
        Args:
            revisions: Ordered list of revision IDs to analyze.
            
        Yields:
            EvolutionStep for each transition.
        """
        # Load the base state (first revision in range)
        current_graph = self.snapshot_engine.get_schema_at_revision(revisions[0])
        
        # Initial step
        yield EvolutionStep(
            revision_id=revisions[0],
            message="Start of range",
            delta=SchemaDelta(revisions[0], revisions[0]), # Empty delta
            table_count=len(current_graph),
        )
        
        # Iterate through rest
        for i in range(1, len(revisions)):
            rev = revisions[i]
            next_graph = self.snapshot_engine.get_schema_at_revision(rev)
            
            delta = self.diff_engine.compute(current_graph, next_graph, revisions[i-1], rev)
            
            yield EvolutionStep(
                revision_id=rev,
                message="", # In a real implementation we'd fetch the commit message
                delta=delta,
                table_count=len(next_graph),
            )
            
            current_graph = next_graph
