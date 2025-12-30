"""Tests for pattern detection helper functions."""

import pytest

from flaqes.analysis.pattern_helpers import (
    add_column_signal,
    check_timestamp_column,
    find_column_by_names,
)
from flaqes.analysis.pattern_matcher import PatternSignal
from flaqes.core.schema_graph import Column, DataType, Table
from flaqes.core.types import DataTypeCategory


class TestFindColumnByNames:
    """Tests for find_column_by_names helper."""

    def test_finds_first_match(self) -> None:
        """Should find first matching column name."""
        col_names = {"id", "name", "email"}
        candidates = {"email", "contact", "phone"}
        
        result = find_column_by_names(col_names, candidates)
        
        assert result == "email"

    def test_returns_none_when_no_match(self) -> None:
        """Should return None when no candidates match."""
        col_names = {"id", "name"}
        candidates = {"email", "phone"}
        
        result = find_column_by_names(col_names, candidates)
        
        assert result is None

    def test_empty_columns(self) -> None:
        """Should return None when column set is empty."""
        col_names = set()
        candidates = {"email", "phone"}
        
        result = find_column_by_names(col_names, candidates)
        
        assert result is None

    def test_empty_candidates(self) -> None:
        """Should return None when candidates set is empty."""
        col_names = {"id", "name"}
        candidates = set()
        
        result = find_column_by_names(col_names, candidates)
        
        assert result is None


class TestAddColumnSignal:
    """Tests for add_column_signal helper."""

    def test_adds_signal_when_column_found(self) -> None:
        """Should add signal and column when column name provided."""
        signals: list[PatternSignal] = []
        related_cols: list[str] = []
        
        add_column_signal(
            signals,
            related_cols,
            "test_signal",
            "Test description",
            0.5,
            "test_column",
        )
        
        assert len(signals) == 1
        assert signals[0].name == "test_signal"
        assert signals[0].description == "Test description"
        assert signals[0].weight == 0.5
        assert signals[0].columns == ("test_column",)
        assert "test_column" in related_cols

    def test_does_nothing_when_column_none(self) -> None:
        """Should not add signal when column name is None."""
        signals: list[PatternSignal] = []
        related_cols: list[str] = []
        
        add_column_signal(
            signals,
            related_cols,
            "test_signal",
            "Test description",
            0.5,
            None,
        )
        
        assert len(signals) == 0
        assert len(related_cols) == 0

    def test_appends_to_existing_lists(self) -> None:
        """Should append to existing signals and columns."""
        signals = [
            PatternSignal("existing", "Existing signal", 0.3, ("existing_col",))
        ]
        related_cols = ["existing_col"]
        
        add_column_signal(
            signals,
            related_cols,
            "new_signal",
            "New description",
            0.7,
            "new_column",
        )
        
        assert len(signals) == 2
        assert len(related_cols) == 2
        assert signals[1].name == "new_signal"
        assert related_cols[1] == "new_column"


class TestCheckTimestampColumn:
    """Tests for check_timestamp_column helper."""

    def test_finds_timestamp_column(self) -> None:
        """Should find timestamp column from candidates."""
        table = Table(
            name="test",
            schema="public",
            columns=[
                Column(
                    name="id",
                    data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER),
                    nullable=False,
                ),
                Column(
                    name="created_at",
                    data_type=DataType(
                        raw="timestamp", category=DataTypeCategory.TIMESTAMP
                    ),
                    nullable=False,
                ),
            ],
        )
        col_names = {"id", "created_at"}
        candidates = {"created_at", "inserted_at"}
        
        result = check_timestamp_column(table, col_names, candidates)
        
        assert result == "created_at"

    def test_finds_date_column(self) -> None:
        """Should find date column as valid timestamp."""
        table = Table(
            name="test",
            schema="public",
            columns=[
                Column(
                    name="birth_date",
                    data_type=DataType(raw="date", category=DataTypeCategory.DATE),
                    nullable=True,
                ),
            ],
        )
        col_names = {"birth_date"}
        candidates = {"birth_date", "dob"}
        
        result = check_timestamp_column(table, col_names, candidates)
        
        assert result == "birth_date"

    def test_returns_none_for_non_timestamp(self) -> None:
        """Should return None if column exists but is not timestamp/date."""
        table = Table(
            name="test",
            schema="public",
            columns=[
                Column(
                    name="status",
                    data_type=DataType(raw="text", category=DataTypeCategory.TEXT),
                    nullable=True,
                ),
            ],
        )
        col_names = {"status"}
        candidates = {"status"}
        
        result = check_timestamp_column(table, col_names, candidates)
        
        assert result is None

    def test_returns_none_when_no_match(self) -> None:
        """Should return None when no candidates match."""
        table = Table(
            name="test",
            schema="public",
            columns=[
                Column(
                    name="created_at",
                    data_type=DataType(
                        raw="timestamp", category=DataTypeCategory.TIMESTAMP
                    ),
                    nullable=False,
                ),
            ],
        )
        col_names = {"created_at"}
        candidates = {"updated_at", "modified_at"}
        
        result = check_timestamp_column(table, col_names, candidates)
        
        assert result is None

    def test_checks_multiple_candidates(self) -> None:
        """Should check multiple candidates and return first match."""
        table = Table(
            name="test",
            schema="public",
            columns=[
                Column(
                    name="updated_at",
                    data_type=DataType(
                        raw="timestamp", category=DataTypeCategory.TIMESTAMP
                    ),
                    nullable=False,
                ),
                Column(
                    name="modified_at",
                    data_type=DataType(
                        raw="timestamp", category=DataTypeCategory.TIMESTAMP
                    ),
                    nullable=False,
                ),
            ],
        )
        col_names = {"updated_at", "modified_at"}
        candidates = {"updated_at", "modified_at"}
        
        result = check_timestamp_column(table, col_names, candidates)
        
        # Should return one of them (order depends on set iteration)
        assert result in {"updated_at", "modified_at"}
