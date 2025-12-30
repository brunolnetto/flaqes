"""Helper functions for pattern detection to reduce complexity."""

from flaqes.analysis.pattern_matcher import PatternSignal
from flaqes.core.schema_graph import Table
from flaqes.core.types import DataTypeCategory


def find_column_by_names(
    col_names: set[str],
    candidate_names: set[str],
) -> str | None:
    """Find first matching column name from candidates."""
    return next((n for n in candidate_names if n in col_names), None)


def add_column_signal(
    signals: list[PatternSignal],
    related_cols: list[str],
    signal_name: str,
    description: str,
    weight: float,
    column_name: str | None,
) -> None:
    """Add a signal and update related columns if column found."""
    if column_name:
        signals.append(
            PatternSignal(
                name=signal_name,
                description=description,
                weight=weight,
                columns=(column_name,),
            )
        )
        related_cols.append(column_name)


def check_timestamp_column(
    table: Table,
    col_names: set[str],
    candidate_names: set[str],
) -> str | None:
    """Check if any candidate column exists and is a timestamp type."""
    columns_by_name = {c.name.lower(): c for c in table.columns}
    
    for name in candidate_names:
        if name in col_names:
            col = columns_by_name[name]
            if col.data_type.category in (
                DataTypeCategory.TIMESTAMP,
                DataTypeCategory.DATE,
            ):
                return name
    return None
