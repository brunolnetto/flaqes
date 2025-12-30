"""
Report generation for Flaikes schema analysis.

This module provides structured reporting for schema analysis results,
including markdown and JSON output formats.
"""

from dataclasses import asdict, dataclass, field
from typing import Any

from flaqes.analysis.pattern_matcher import DetectedPattern, PatternDetector
from flaqes.analysis.role_detector import RoleDetector, TableRoleResult
from flaqes.analysis.tension_analyzer import DesignTension, TensionAnalyzer
from flaqes.core.intent import Intent
from flaqes.core.schema_graph import SchemaGraph


@dataclass
class SchemaReport:
    """Complete analysis report for a database schema."""

    schema_name: str
    table_count: int
    intent: Intent | None = None

    # Analysis results
    table_roles: dict[str, TableRoleResult] = field(default_factory=dict)
    patterns: dict[str, list[DetectedPattern]] = field(default_factory=dict)
    tensions: dict[str, list[DesignTension]] = field(default_factory=dict)

    # Summary statistics
    role_summary: dict[str, int] = field(default_factory=dict)
    pattern_summary: dict[str, int] = field(default_factory=dict)
    tension_summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            "schema_name": self.schema_name,
            "table_count": self.table_count,
            "intent": asdict(self.intent) if self.intent else None,
            "table_roles": {
                table: {
                    "role": result.primary_role.name,
                    "confidence": result.confidence,
                    "signals": [s.name for s in result.signals],
                }
                for table, result in self.table_roles.items()
            },
            "patterns": {
                table: [
                    {
                        "type": p.pattern_type.name,
                        "confidence": p.confidence,
                        "columns": list(p.related_columns),
                    }
                    for p in patterns
                ]
                for table, patterns in self.patterns.items()
            },
            "tensions": {
                table: [
                    {
                        "id": t.id,
                        "category": t.category.name,
                        "severity": t.severity.name,
                        "description": t.description,
                        "risk": t.risk,
                    }
                    for t in tensions
                ]
                for table, tensions in self.tensions.items()
            },
            "summary": {
                "roles": self.role_summary,
                "patterns": self.pattern_summary,
                "tensions": self.tension_summary,
            },
        }

    def to_markdown(self) -> str:
        """Generate a markdown report."""
        lines = []

        # Header
        lines.append(f"# Schema Analysis Report: {self.schema_name}")
        lines.append("")
        lines.append(f"**Tables analyzed:** {self.table_count}")

        if self.intent:
            lines.append(f"**Workload:** {self.intent.workload}")
            lines.append(f"**Data volume:** {self.intent.data_volume}")
            lines.append(f"**Write frequency:** {self.intent.write_frequency}")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")

        if self.role_summary:
            lines.append("### Table Roles")
            for role, count in sorted(self.role_summary.items(), key=lambda x: -x[1]):
                lines.append(f"- **{role}**: {count}")
            lines.append("")

        if self.pattern_summary:
            lines.append("### Design Patterns")
            for pattern, count in sorted(
                self.pattern_summary.items(), key=lambda x: -x[1]
            ):
                lines.append(f"- **{pattern}**: {count}")
            lines.append("")

        if self.tension_summary:
            lines.append("### Design Tensions")
            critical = self.tension_summary.get("critical", 0)
            warning = self.tension_summary.get("warning", 0)
            info = self.tension_summary.get("info", 0)

            if critical > 0:
                lines.append(f"- 🔴 **Critical**: {critical}")
            if warning > 0:
                lines.append(f"- 🟡 **Warning**: {warning}")
            if info > 0:
                lines.append(f"- 🔵 **Info**: {info}")
            lines.append("")

        lines.append("---")
        lines.append("")

        # Detailed tensions (most important)
        if self.tensions:
            lines.append("## Design Tensions")
            lines.append("")

            # Group by severity
            critical_tensions = []
            warning_tensions = []
            info_tensions = []

            for table, table_tensions in self.tensions.items():
                for t in table_tensions:
                    if t.is_critical:
                        critical_tensions.append((table, t))
                    elif t.is_warning:
                        warning_tensions.append((table, t))
                    else:
                        info_tensions.append((table, t))

            if critical_tensions:
                lines.append("### 🔴 Critical Issues")
                lines.append("")
                for table, t in critical_tensions:
                    lines.append(f"#### {table}: {t.description}")
                    lines.append(f"**Risk:** {t.risk}")
                    lines.append(f"**Breaking point:** {t.breaking_point}")
                    if t.alternatives:
                        lines.append(f"**Alternatives:** {len(t.alternatives)}")
                        for alt in t.alternatives[:2]:  # Show top 2
                            lines.append(
                                f"- {alt.description} ({alt.effort.value} effort)"
                            )
                    lines.append("")

            if warning_tensions:
                lines.append("### 🟡 Warnings")
                lines.append("")
                for table, t in warning_tensions:
                    lines.append(f"#### {table}: {t.description}")
                    lines.append(f"**Risk:** {t.risk}")
                    lines.append("")

        # Table details
        if self.table_roles:
            lines.append("---")
            lines.append("")
            lines.append("## Table Analysis")
            lines.append("")

            for table, role_result in sorted(self.table_roles.items()):
                lines.append(f"### {table}")
                lines.append(
                    f"**Role:** {role_result.primary_role.name} ({role_result.confidence:.0%} confidence)"
                )

                # Patterns
                if table in self.patterns and self.patterns[table]:
                    lines.append(f"**Patterns detected:** {len(self.patterns[table])}")
                    for p in self.patterns[table][:3]:  # Top 3
                        lines.append(f"- {p.pattern_type.name} ({p.confidence:.0%})")

                # Tensions count
                if table in self.tensions and self.tensions[table]:
                    lines.append(f"**Design tensions:** {len(self.tensions[table])}")

                lines.append("")

        return "\n".join(lines)


def generate_report(
    graph: SchemaGraph,
    intent: Intent | None = None,
) -> SchemaReport:
    """Generate a complete analysis report for a schema.

    Args:
        graph: The schema graph to analyze.
        intent: Optional intent to inform severity scoring.

    Returns:
        Complete SchemaReport with all analysis results.
    """
    # Run analysis
    role_detector = RoleDetector()
    pattern_detector = PatternDetector()
    tension_analyzer = TensionAnalyzer(intent=intent)

    # Detect roles
    table_roles = {}
    for table in graph:
        role_result = role_detector.detect(table, graph)
        table_roles[table.fqn] = role_result

    # Detect patterns
    patterns = pattern_detector.detect_schema_patterns(graph)

    # Detect tensions
    tensions = tension_analyzer.analyze(graph)

    # Calculate summaries
    role_summary: dict[str, int] = {}
    for result in table_roles.values():
        role_name = result.primary_role.name
        role_summary[role_name] = role_summary.get(role_name, 0) + 1

    pattern_summary: dict[str, int] = {}
    for table_patterns in patterns.values():
        for p in table_patterns:
            pattern_name = p.pattern_type.name
            pattern_summary[pattern_name] = pattern_summary.get(pattern_name, 0) + 1

    tension_summary = tension_analyzer.get_summary(graph)

    # Get schema name from first table
    schema_name = "unknown"
    if graph.tables:
        first_table = next(iter(graph.tables.values()))
        schema_name = first_table.schema

    return SchemaReport(
        schema_name=schema_name,
        table_count=len(graph.tables),
        intent=intent,
        table_roles=table_roles,
        patterns=patterns,
        tensions=tensions,
        role_summary=role_summary,
        pattern_summary=pattern_summary,
        tension_summary=tension_summary,
    )
