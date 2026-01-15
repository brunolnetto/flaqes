"""Tests for report generation."""

import json

import pytest

from flaqes.core.intent import Intent
from flaqes.core.schema_graph import Column, DataType, PrimaryKey, SchemaGraph, Table
from flaqes.core.types import DataTypeCategory
from flaqes.report import SchemaReport, generate_report


def make_simple_graph() -> SchemaGraph:
    """Create a simple schema graph for testing."""
    table1 = Table(
        name="users",
        schema="public",
        columns=[
            Column(
                name="id",
                data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER),
                nullable=False,
            ),
            Column(
                name="email",
                data_type=DataType(raw="text", category=DataTypeCategory.TEXT),
                nullable=False,
            ),
            Column(
                name="created_at",
                data_type=DataType(raw="timestamp", category=DataTypeCategory.TIMESTAMP),
                nullable=False,
            ),
        ],
        primary_key=PrimaryKey(name="users_pkey", columns=("id",)),
    )
    
    table2 = Table(
        name="orders",
        schema="public",
        columns=[
            Column(
                name="id",
                data_type=DataType(raw="integer", category=DataTypeCategory.INTEGER),
                nullable=False,
            ),
            Column(
                name="total",
                data_type=DataType(raw="numeric", category=DataTypeCategory.DECIMAL),
                nullable=False,
            ),
            Column(
                name="created_at",
                data_type=DataType(raw="timestamp", category=DataTypeCategory.TIMESTAMP),
                nullable=False,
            ),
            Column(
                name="updated_at",
                data_type=DataType(raw="timestamp", category=DataTypeCategory.TIMESTAMP),
                nullable=False,
            ),
        ],
        primary_key=PrimaryKey(name="orders_pkey", columns=("id",)),
    )
    
    return SchemaGraph.from_tables([table1, table2])


class TestSchemaReport:
    """Tests for SchemaReport dataclass."""

    def test_report_creation(self) -> None:
        """SchemaReport should be creatable."""
        report = SchemaReport(
            schema_name="public",
            table_count=5,
        )
        
        assert report.schema_name == "public"
        assert report.table_count == 5

    def test_to_dict(self) -> None:
        """to_dict should produce serializable dict."""
        report = SchemaReport(
            schema_name="public",
            table_count=2,
            role_summary={"FACT": 1, "DIMENSION": 1},
        )
        
        result = report.to_dict()
        
        assert result["schema_name"] == "public"
        assert result["table_count"] == 2
        assert "summary" in result
        
        # Should be JSON serializable
        json_str = json.dumps(result)
        assert json_str is not None

    def test_to_dict_with_intent(self) -> None:
        """to_dict should include intent if provided."""
        intent = Intent(
            workload="OLTP",
            write_frequency="high",
            read_patterns=["point_lookup"],
            consistency="strong",
            evolution_rate="medium",
            data_volume="medium",
            engine="postgresql",
        )
        
        report = SchemaReport(
            schema_name="public",
            table_count=1,
            intent=intent,
        )
        
        result = report.to_dict()
        
        assert result["intent"] is not None
        assert result["intent"]["workload"] == "OLTP"

    def test_to_markdown_basic(self) -> None:
        """to_markdown should produce readable markdown."""
        report = SchemaReport(
            schema_name="mydb",
            table_count=3,
            role_summary={"FACT": 2, "DIMENSION": 1},
        )
        
        markdown = report.to_markdown()
        
        assert "# Schema Analysis Report: mydb" in markdown
        assert "**Tables analyzed:** 3" in markdown
        assert "FACT" in markdown
        assert "DIMENSION" in markdown

    def test_to_markdown_with_intent(self) -> None:
        """to_markdown should include intent details."""
        intent = Intent(
            workload="OLAP",
            write_frequency="low",
            read_patterns=["aggregation"],
            consistency="eventual",
            evolution_rate="low",
            data_volume="large",
            engine="postgresql",
        )
        
        report = SchemaReport(
            schema_name="warehouse",
            table_count=10,
            intent=intent,
        )
        
        markdown = report.to_markdown()
        
        assert "OLAP" in markdown
        assert "large" in markdown

    def test_to_markdown_with_tensions(self) -> None:
        """to_markdown should include tension details."""
        from flaqes.analysis.tension_analyzer import DesignTension
        from flaqes.core.types import Severity, TensionCategory
        
        tension = DesignTension(
            id="test",
            category=TensionCategory.PERFORMANCE,
            description="Missing index",
            current_benefit="None",
            risk="Slow queries",
            breaking_point="10K rows",
            severity=Severity.CRITICAL,
            table="public.orders",
        )
        
        report = SchemaReport(
            schema_name="public",
            table_count=1,
            tensions={"public.orders": [tension]},
            tension_summary={"critical": 1},
        )
        
        markdown = report.to_markdown()
        
        assert "Critical" in markdown or "🔴" in markdown
        assert "Missing index" in markdown


class TestGenerateReport:
    """Tests for generate_report function."""

    def test_generate_report_runs(self) -> None:
        """generate_report should complete without errors."""
        graph = make_simple_graph()
        
        report = generate_report(graph)
        
        assert report.table_count == 2
        assert report.schema_name == "public"

    def test_generate_report_with_intent(self) -> None:
        """generate_report should use intent for analysis."""
        graph = make_simple_graph()
        intent = Intent(
            workload="OLTP",
            write_frequency="high",
            read_patterns=["point_lookup"],
            consistency="strong",
            evolution_rate="medium",
            data_volume="medium",
            engine="postgresql",
        )
        
        report = generate_report(graph, intent)
        
        assert report.intent == intent

    def test_generate_report_detects_roles(self) -> None:
        """generate_report should detect table roles."""
        graph = make_simple_graph()
        
        report = generate_report(graph)
        
        # Should have analyzed both tables
        assert len(report.table_roles) == 2
        assert "public.users" in report.table_roles
        assert "public.orders" in report.table_roles

    def test_generate_report_detects_patterns(self) -> None:
        """generate_report should detect patterns."""
        graph = make_simple_graph()
        
        report = generate_report(graph)
        
        # Both tables have created_at, should detect audit pattern
        assert len(report.patterns) >= 1

    def test_generate_report_has_summaries(self) -> None:
        """generate_report should include summary statistics."""
        graph = make_simple_graph()
        
        report = generate_report(graph)
        
        assert report.role_summary is not None
        assert report.pattern_summary is not None
        assert report.tension_summary is not None

    def test_report_is_json_serializable(self) -> None:
        """Generated report should be JSON serializable."""
        graph = make_simple_graph()
        report = generate_report(graph)
        
        report_dict = report.to_dict()
        json_str = json.dumps(report_dict, indent=2)
        
        assert json_str is not None
        assert len(json_str) > 0

    def test_report_markdown_is_readable(self) -> None:
        """Generated markdown should be well-formatted."""
        graph = make_simple_graph()
        report = generate_report(graph)
        
        markdown = report.to_markdown()
        
        # Should have header
        assert markdown.startswith("#")
        # Should have table analysis
        assert "public.users" in markdown or "users" in markdown
        # Should be multi-line
        assert "\n" in markdown
