<<<<<<< HEAD:flaqes/cli.py
"""
Command-line interface for flaqes.

Provides commands for analyzing database schemas.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import TYPE_CHECKING

from importlib import metadata

try:
    __version__ = metadata.version("flaqes")
except metadata.PackageNotFoundError:
    __version__ = "0.0.0-dev"


if TYPE_CHECKING:
    pass


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="flaqes",
        description="A schema critic for databases - analyze structure, surface trade-offs, propose alternatives",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Analyze command (live database)
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze a database schema",
    )
    analyze_parser.add_argument(
        "dsn",
        help="Database connection string (e.g., postgresql://user:pass@host/db)",
    )
    analyze_parser.add_argument(
        "--workload",
        choices=["OLTP", "OLAP", "mixed"],
        default="mixed",
        help="Primary workload type (default: mixed)",
    )
    analyze_parser.add_argument(
        "--volume",
        choices=["small", "medium", "large", "massive"],
        default="medium",
        help="Data volume classification (default: medium)",
    )
    analyze_parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    analyze_parser.add_argument(
        "--tables",
        nargs="*",
        help="Specific tables to analyze (default: all)",
    )
    analyze_parser.add_argument(
        "--schemas",
        nargs="*",
        help="Schemas to include (default: public)",
    )
    
    # Analyze DDL command (offline)
    ddl_parser = subparsers.add_parser(
        "analyze-ddl",
        help="Analyze DDL file(s) without database connection",
    )
    ddl_parser.add_argument(
        "files",
        nargs="+",
        help="DDL file(s) to analyze (SQL files with CREATE TABLE statements)",
    )
    ddl_parser.add_argument(
        "--workload",
        choices=["OLTP", "OLAP", "mixed"],
        default="mixed",
        help="Primary workload type (default: mixed)",
    )
    ddl_parser.add_argument(
        "--volume",
        choices=["small", "medium", "large", "massive"],
        default="medium",
        help="Data volume classification (default: medium)",
    )
    ddl_parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    ddl_parser.add_argument(
        "--schema",
        default="public",
        help="Default schema name (default: public)",
    )

    # Analyze Revision (Evolution / Snapshot)
    rev_parser = subparsers.add_parser(
        "analyze-rev",
        help="Analyze a specific schema revision (requires Alembic)",
    )
    rev_parser.add_argument(
        "revision",
        help="Revision ID to analyze (e.g., 'head', 'base', '1a2b3c')",
    )
    rev_parser.add_argument(
        "--config",
        default="alembic.ini",
        help="Path to alembic.ini (default: alembic.ini)",
    )
    rev_parser.add_argument(
        "--workload",
        choices=["OLTP", "OLAP", "mixed"],
        default="mixed",
        help="Primary workload type (default: mixed)",
    )
    rev_parser.add_argument(
        "--volume",
        choices=["small", "medium", "large", "massive"],
        default="medium",
        help="Data volume classification (default: medium)",
    )
    rev_parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )

    # Diff Command (Evolution)
    diff_parser = subparsers.add_parser(
        "diff",
        help="Compare two schema revisions (requires Alembic)",
    )
    diff_parser.add_argument(
        "base_rev",
        help="Base revision (e.g., 'base')",
    )
    diff_parser.add_argument(
        "head_rev",
        help="Head revision (e.g., 'head') to compare against",
    )
    diff_parser.add_argument(
        "--config",
        default="alembic.ini",
        help="Path to alembic.ini (default: alembic.ini)",
    )
    diff_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    # Evolution Command
    evo_parser = subparsers.add_parser(
        "evolution",
        help="Analyze schema evolution over a range of revisions",
    )
    evo_parser.add_argument(
        "--config",
        default="alembic.ini",
        help="Path to alembic.ini (default: alembic.ini)",
    )
    evo_parser.add_argument(
        "--history-path",
        help="Path to alembic versions directory (to discover inputs)",
    )
    evo_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of revisions to analyze (default: 10)",
    )
    
    # Introspect command (lower-level)
    introspect_parser = subparsers.add_parser(
        "introspect",
        help="Introspect a database schema (raw output)",
    )
    introspect_parser.add_argument(
        "--dsn",
        required=True,
        help="Database connection string",
    )
    introspect_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    
    # Diagram command (Mermaid ERD)
    diagram_parser = subparsers.add_parser(
        "diagram",
        help="Generate a Mermaid ERD diagram from a database or DDL file",
    )
    diagram_parser.add_argument(
        "--dsn",
        help="Database connection string (mutually exclusive with --ddl)",
    )
    diagram_parser.add_argument(
        "--ddl",
        help="Path to DDL file (mutually exclusive with --dsn)",
    )
    diagram_parser.add_argument(
        "--no-columns",
        action="store_true",
        help="Exclude column definitions (show only tables and relationships)",
    )
    diagram_parser.add_argument(
        "--no-types",
        action="store_true",
        help="Exclude column types",
    )
    diagram_parser.add_argument(
        "--max-columns",
        type=int,
        default=None,
        help="Maximum columns to show per table (default: show all)",
    )
    diagram_parser.add_argument(
        "--wrap",
        action="store_true",
        help="Wrap output in markdown code block",
    )

    # History command (Barmaid integration)
    history_parser = subparsers.add_parser(
        "history",
        help="Visualize migration history (requires Alembic versions directory)",
    )
    history_parser.add_argument(
        "path",
        nargs="?",
        help="Path to the alembic 'versions' directory",
    )
    history_parser.add_argument(
        "-o", "--output",
        help="Save the diagram to a file",
    )
    history_parser.add_argument(
        "-d", "--direction",
        choices=["TD", "LR", "BT", "RL"],
        default="TD",
        help="The direction of the flowchart (default: TD)",
    )
    history_parser.add_argument(
        "--no-orphans",
        action="store_false",
        dest="show_orphans",
        help="Don't show missing parent revisions",
    )
    history_parser.add_argument(
        "--wrap",
        action="store_true",
        help="Wrap output in markdown code block",
    )
    
    return parser


async def run_analyze(args: argparse.Namespace) -> int:
    """Run the analyze command."""
    try:
        from flaqes import Intent, analyze_schema
        
        intent = Intent(
            workload=args.workload,
            data_volume=args.volume,
        )
        
        report = await analyze_schema(
            dsn=args.dsn,
            intent=intent,
            tables=args.tables,
            schemas=args.schemas,
        )
        
        if args.format == "json":
            import json
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(report.to_markdown())
        
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def run_analyze_ddl(args: argparse.Namespace) -> int:
    """Run the analyze-ddl command."""
    try:
        from flaqes import Intent, generate_report, parse_ddl
        
        # Read and combine all DDL files
        combined_ddl = ""
        for filepath in args.files:
            with open(filepath, encoding="utf-8") as f:
                combined_ddl += f.read() + "\n"
        
        # Parse DDL
        graph = parse_ddl(combined_ddl, default_schema=args.schema)
        
        # Create intent
        intent = Intent(
            workload=args.workload,
            data_volume=args.volume,
        )
        
        # Generate report
        report = generate_report(graph, intent=intent)
        
        if args.format == "json":
            import json
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(report.to_markdown())
        
        return 0
    except FileNotFoundError as e:
        print(f"Error: File not found - {e.filename}", file=sys.stderr)
        return 1
    except Exception as e:  # pragma: no cover
        print(f"Error: {e}", file=sys.stderr)
        return 1


def run_diff(args: argparse.Namespace) -> int:
    """Run the diff command."""
    try:
        from flaqes.evolution import SnapshotEngine, SnapshotError, DiffEngine
        
        engine = SnapshotEngine(args.config)
        
        # 1. Get both snapshots
        try:
            print(f"Generating snapshot for {args.base_rev}...", file=sys.stderr)
            base_graph = engine.get_schema_at_revision(args.base_rev)
            
            print(f"Generating snapshot for {args.head_rev}...", file=sys.stderr)
            head_graph = engine.get_schema_at_revision(args.head_rev)
            
        except ImportError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except SnapshotError as e:
            print(f"Error: Snapshot generation failed - {e}", file=sys.stderr)
            return 1
            
        # 2. Compute Diff
        diff_engine = DiffEngine()
        delta = diff_engine.compute(base_graph, head_graph, args.base_rev, args.head_rev)
        
        # 3. Output
        if args.format == "json":
            import json
            from dataclasses import asdict
            print(json.dumps(asdict(delta), indent=2))
        else:
            print(f"# Schema Diff: {args.base_rev} -> {args.head_rev}\n")
            if not delta.has_changes():
                print("No structural changes detected.")
            else:
                if delta.added_tables:
                    print(f"## Added Tables ({len(delta.added_tables)})")
                    for t in delta.added_tables:
                        print(f"+ {t}")
                    print()
                
                if delta.removed_tables:
                    print(f"## Removed Tables ({len(delta.removed_tables)})")
                    for t in delta.removed_tables:
                        print(f"- {t}")
                    print()
                    
                if delta.modified_tables:
                    print(f"## Modified Tables ({len(delta.modified_tables)})")
                    for t in delta.modified_tables:
                        print(f"~ {t}")
                    print()
                
                if delta.role_drifts:
                    print(f"## Semantic Role Drift ({len(delta.role_drifts)})")
                    for d in delta.role_drifts:
                        print(f"* {d.table_name}: {d.description}")
                    print()
        
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def run_evolution(args: argparse.Namespace) -> int:
    """Run the evolution command."""
    try:
        from flaqes.evolution import SnapshotEngine, SnapshotError, EvolutionReportEngine
        from flaqes.visualization import sparkline, format_trend
        from pathlib import Path
        
        # 1. Discover revisions (simple implementation: list file names)
        # Ideally we'd use barmaid or alembic to get the DAG, but for now 
        # let's assume we can get a list. Since we don't want to duplicate logic,
        # we will just placeholder this for now or try to use barmaid if present.
        revisions = []
        try:
             # Try to use barmaid to get sorted revisions
            from barmaid.cli import parse_migration_file
            
            # Find versions dir
            versions_dir = None
            if args.history_path:
                versions_dir = Path(args.history_path)
            else:
                 # Search typical paths
                for p in [Path("alembic/versions"), Path("versions"), Path("src/backend/alembic/versions")]:
                    if p.exists():
                        versions_dir = p
                        break
            
            if versions_dir: 
                # Very naive sort by filename prefix (Alembic usually timestamps)
                # Proper DAG traversal is harder without full barmaid integration
                files = sorted(list(versions_dir.glob("*.py")))
                for f in files:
                    m = parse_migration_file(f)
                    if m['revision']:
                        revisions.append(m['revision'])
        except ImportError:
            print("Warning: 'barmaid' not found, cannot auto-discover revisions correctly.", file=sys.stderr)
            
        if not revisions:
            print("Error: No revisions found. Please install barmaid or specify path.", file=sys.stderr)
            return 1
            
        # Limit revisions
        if args.limit:
            revisions = revisions[-args.limit:]
            
        print(f"Analyzing last {len(revisions)} revisions...", file=sys.stderr)

        engine = SnapshotEngine(args.config)
        report_engine = EvolutionReportEngine(engine)
        
        steps = []
        try:
            for step in report_engine.analyze_range(revisions):
                steps.append(step)
                print(".", end="", file=sys.stderr, flush=True) # Progress
        except Exception as e:
            print(f"\nError during analysis: {e}", file=sys.stderr)
            return 1
            
        print("\n", file=sys.stderr)
        
        # Output Report
        print(f"# Evolution Report ({len(revisions)} revisions)\n")
        
        # Sparkline
        counts = [s.table_count for s in steps]
        print(f"Table Count Trend: {sparkline(counts)} ({counts[0]} -> {counts[-1]})")
        print()
        
        print("| Revision | Tables | Delta |")
        print("| :--- | :--- | :--- |")
        
        prev_count = steps[0].table_count
        for step in steps:
            trend = format_trend(step.table_count, prev_count)
            # Summarize delta
            delta_summary = []
            if step.delta.added_tables:
                delta_summary.append(f"+{len(step.delta.added_tables)} tbl")
            if step.delta.removed_tables:
                delta_summary.append(f"-{len(step.delta.removed_tables)} tbl")
            if step.delta.role_drifts:
                 delta_summary.append(f"🕸️ {len(step.delta.role_drifts)} drifts")
                 
            delta_str = ", ".join(delta_summary) if delta_summary else "-"
            
            print(f"| `{step.revision_id}` | {trend} | {delta_str} |")
            prev_count = step.table_count
            
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def run_analyze_rev(args: argparse.Namespace) -> int:
    """Run the analyze-rev command."""
    try:
        from flaqes import Intent, generate_report
        from flaqes.evolution import SnapshotEngine, SnapshotError
        
        # 1. Generate Schema Snapshot
        try:
            engine = SnapshotEngine(args.config)
            graph = engine.get_schema_at_revision(args.revision)
        except ImportError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except SnapshotError as e:
            print(f"Error: Snapshot generation failed - {e}", file=sys.stderr)
            return 1
            
        # 2. Analyze
        intent = Intent(
            workload=args.workload,
            data_volume=args.volume,
        )
        report = generate_report(graph, intent=intent)
        
        # 3. Output
        if args.format == "json":
            import json
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(f"# Analysis for Revision: {args.revision}\n")
            print(report.to_markdown())
            
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


async def run_introspect(args: argparse.Namespace) -> int:
    """Run the introspect command."""
    try:
        from flaqes import introspect_schema
        
        graph = await introspect_schema(dsn=args.dsn)
        
        if args.format == "json":
            import json
            # Basic JSON output of schema structure
            output = {
                "tables": [
                    {
                        "name": table.name,
                        "schema": table.schema,
                        "columns": [col.name for col in table.columns],
                        "primary_key": list(table.primary_key.columns) if table.primary_key else None,
                        "foreign_keys": len(table.foreign_keys),
                        "indexes": len(table.indexes),
                    }
                    for table in graph
                ]
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"Schema introspection: {len(list(graph))} tables found\n")
            for table in graph:
                pk_info = f" (PK: {', '.join(table.primary_key.columns)})" if table.primary_key else ""
                print(f"  {table.fqn}{pk_info}")
                print(f"    Columns: {len(table.columns)}")
                print(f"    Foreign Keys: {len(table.foreign_keys)}")
                print(f"    Indexes: {len(table.indexes)}")
                print()
        
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


async def run_diagram(args: argparse.Namespace) -> int:
    """Run the diagram command."""
    try:
        # Validate that exactly one of --dsn or --ddl is provided
        if not args.dsn and not args.ddl:
            print("Error: Either --dsn or --ddl is required", file=sys.stderr)
            return 1
        if args.dsn and args.ddl:
            print("Error: Cannot use both --dsn and --ddl", file=sys.stderr)
            return 1
        
        # Get the schema graph
        if args.dsn:  # pragma: no cover (integration test required)
            from flaqes import introspect_schema
            graph = await introspect_schema(dsn=args.dsn)
        else:
            from flaqes.introspection.ddl_parser import parse_ddl_file
            graph = parse_ddl_file(args.ddl)
        
        # Generate the Mermaid ERD
        mermaid = graph.to_mermaid_erd(
            include_columns=not args.no_columns,
            max_columns=args.max_columns,
            show_types=not args.no_types,
        )
        
        # Optionally wrap in markdown code block
        if args.wrap:
            print("```mermaid")
            print(mermaid)
            print("```")
        else:
            print(mermaid)
        
        return 0
    except Exception as e:  # pragma: no cover
        print(f"Error: {e}", file=sys.stderr)
        return 1


def run_history(args: argparse.Namespace) -> int:
    """Run the history command (integrates barmaid)."""
    try:
        from pathlib import Path
        from barmaid.cli import parse_migration_file, generate_mermaid_diagram
        
        # Logic adapted from barmaid's main
        versions_dir = None
        if args.path:
            versions_dir = Path(args.path)
        else:
            search_paths = [
                Path('alembic/versions'),
                Path('versions'),
                Path('src/backend/alembic/versions'),
                Path('backend/alembic/versions'),
            ]
            for p in search_paths:
                if p.exists() and p.is_dir():
                    versions_dir = p
                    break
        
        if not versions_dir or not versions_dir.exists():
            print("Error: Could not find versions directory. Provide path as argument.", file=sys.stderr)
            return 1
            
        migrations = []
        for filepath in sorted(versions_dir.glob('*.py')):
            if filepath.name == '__init__.py':
                continue
            try:
                mig = parse_migration_file(filepath)
                if mig['revision']:
                    migrations.append(mig)
            except Exception as e:
                print(f"Warning: Could not parse {filepath.name}: {e}", file=sys.stderr)
        
        if not migrations:
            print("No migrations found!", file=sys.stderr)
            return 1
            
        diagram = generate_mermaid_diagram(
            migrations,
            direction=args.direction,
            show_orphans=getattr(args, 'show_orphans', True)
        )
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(diagram)
            print(f"History diagram saved to {args.output}", file=sys.stderr)
        else:
            if args.wrap:
                print("```mermaid")
                print(diagram)
                print("```")
            else:
                print(diagram)
        
        return 0
    except ImportError:
        print("Error: 'barmaid' package not found. Install it with 'pip install barmaid'.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 0
    
    if args.command == "analyze":
        return asyncio.run(run_analyze(args))
    elif args.command == "analyze-ddl":
        return run_analyze_ddl(args)
    elif args.command == "analyze-rev":
        return run_analyze_rev(args)
    elif args.command == "diff":
        return run_diff(args)
    elif args.command == "evolution":
        return run_evolution(args)
    elif args.command == "introspect":
        return asyncio.run(run_introspect(args))
    elif args.command == "diagram":
        return asyncio.run(run_diagram(args))
    elif args.command == "history":
        return run_history(args)
    
    parser.print_help()  # pragma: no cover
    return 0  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

=======
"""
Command-line interface for flakes.

This module provides a CLI for analyzing database schemas from the command line.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import NoReturn

from flakes import Intent, analyze_schema
from flakes.core.intent import (
    OLAP_INTENT,
    OLTP_INTENT,
    EVENT_SOURCING_INTENT,
    STARTUP_MVP_INTENT,
)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="flakes",
        description="A schema critic for PostgreSQL databases - analyze structure, surface trade-offs, propose alternatives",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze entire database with default intent
  flakes analyze postgresql://user:pass@localhost/mydb

  # Analyze with OLAP intent
  flakes analyze --intent olap postgresql://localhost/mydb

  # Analyze specific tables only
  flakes analyze --tables users,orders,products postgresql://localhost/mydb

  # Output JSON instead of Markdown
  flakes analyze --format json --output report.json postgresql://localhost/mydb

  # Use custom intent
  flakes analyze --workload OLTP --write-frequency high postgresql://localhost/mydb

For more information, visit: https://github.com/your-org/flakes
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze a database schema",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Positional argument: DSN
    analyze_parser.add_argument(
        "dsn",
        help="Database connection string (e.g., postgresql://user:pass@host/db)",
    )

    # Intent selection (presets or custom)
    intent_group = analyze_parser.add_argument_group("Intent (choose preset or custom)")
    intent_group.add_argument(
        "--intent",
        choices=["oltp", "olap", "event-sourcing", "startup-mvp"],
        help="Use a predefined intent preset",
    )
    intent_group.add_argument(
        "--workload",
        choices=["OLTP", "OLAP", "mixed"],
        help="Workload type (custom intent)",
    )
    intent_group.add_argument(
        "--write-frequency",
        choices=["high", "medium", "low"],
        help="Write frequency (custom intent)",
    )
    intent_group.add_argument(
        "--read-patterns",
        help="Comma-separated read patterns: point_lookup,range_scan,aggregation,join_heavy",
    )
    intent_group.add_argument(
        "--consistency",
        choices=["strong", "eventual"],
        help="Consistency level (custom intent)",
    )
    intent_group.add_argument(
        "--evolution-rate",
        choices=["high", "medium", "low", "frozen"],
        help="Schema evolution rate (custom intent)",
    )
    intent_group.add_argument(
        "--data-volume",
        choices=["small", "medium", "large", "massive"],
        help="Data volume (custom intent)",
    )

    # Filtering options
    filter_group = analyze_parser.add_argument_group("Filtering")
    filter_group.add_argument(
        "--tables",
        help="Comma-separated list of tables to analyze (default: all tables)",
    )
    filter_group.add_argument(
        "--schemas",
        help="Comma-separated list of schemas to include (default: public)",
    )
    filter_group.add_argument(
        "--exclude",
        help="Comma-separated patterns to exclude (e.g., tmp_*,staging_*)",
    )

    # Output options
    output_group = analyze_parser.add_argument_group("Output")
    output_group.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    output_group.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file (default: stdout)",
    )
    output_group.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output with detailed signals",
    )
    output_group.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Minimal output (summary only)",
    )

    # version command
    subparsers.add_parser("version", help="Show version information")

    return parser


def parse_read_patterns(patterns_str: str) -> tuple[str, ...]:
    """Parse comma-separated read patterns."""
    valid_patterns = {"point_lookup", "range_scan", "aggregation", "join_heavy"}
    patterns = [p.strip() for p in patterns_str.split(",")]
    
    for pattern in patterns:
        if pattern not in valid_patterns:
            print(f"Error: Invalid read pattern '{pattern}'", file=sys.stderr)
            print(f"Valid patterns: {', '.join(valid_patterns)}", file=sys.stderr)
            sys.exit(1)
    
    return tuple(patterns)


def get_intent_from_args(args: argparse.Namespace) -> Intent | None:
    """Build Intent from command-line arguments."""
    # Check for preset intent
    if args.intent:
        presets = {
            "oltp": OLTP_INTENT,
            "olap": OLAP_INTENT,
            "event-sourcing": EVENT_SOURCING_INTENT,
            "startup-mvp": STARTUP_MVP_INTENT,
        }
        intent = presets[args.intent]
        print(f"Using {args.intent.upper()} intent preset", file=sys.stderr)
        return intent

    # Check for custom intent
    if any([
        args.workload,
        args.write_frequency,
        args.read_patterns,
        args.consistency,
        args.evolution_rate,
        args.data_volume,
    ]):
        # Build custom intent
        read_patterns = ("point_lookup",)
        if args.read_patterns:
            read_patterns = parse_read_patterns(args.read_patterns)
        
        intent = Intent(
            workload=args.workload or "mixed",
            write_frequency=args.write_frequency or "medium",
            read_patterns=read_patterns,
            consistency=args.consistency or "strong",
            evolution_rate=args.evolution_rate or "medium",
            data_volume=args.data_volume or "medium",
        )
        print("Using custom intent", file=sys.stderr)
        return intent
    
    # No intent specified - use defaults
    return None


async def cmd_analyze(args: argparse.Namespace) -> int:
    """Execute the analyze command."""
    try:
        # Get intent
        intent = get_intent_from_args(args)
        
        # Parse filtering options
        tables = None
        if args.tables:
            tables = [t.strip() for t in args.tables.split(",")]
        
        schemas = None
        if args.schemas:
            schemas = [s.strip() for s in args.schemas.split(",")]
        
        exclude_patterns = None
        if args.exclude:
            exclude_patterns = [p.strip() for p in args.exclude.split(",")]
        
        # Print progress
        if not args.quiet:
            print(f"🔍 Analyzing database schema...", file=sys.stderr)
            if intent:
                print(f"   Intent: {intent.summary()}", file=sys.stderr)
            if tables:
                print(f"   Tables: {', '.join(tables)}", file=sys.stderr)
            print("", file=sys.stderr)
        
        # Run analysis
        report = await analyze_schema(
            dsn=args.dsn,
            intent=intent,
            tables=tables,
            schemas=schemas,
            exclude_patterns=exclude_patterns,
        )
        
        # Generate output
        if args.format == "json":
            output = json.dumps(report.to_dict(), indent=2)
        else:
            output = report.to_markdown()
        
        # Write output
        if args.output:
            args.output.write_text(output)
            if not args.quiet:
                print(f"✅ Report saved to {args.output}", file=sys.stderr)
        else:
            print(output)
        
        # Print summary to stderr if not quiet
        if not args.quiet and args.output:
            print("", file=sys.stderr)
            print(f"📊 Summary:", file=sys.stderr)
            print(f"   Tables analyzed: {report.table_count}", file=sys.stderr)
            if report.role_summary:
                print(f"   Roles detected: {len(report.role_summary)}", file=sys.stderr)
            if report.pattern_summary:
                print(f"   Patterns found: {sum(report.pattern_summary.values())}", file=sys.stderr)
            if report.tension_summary:
                total_tensions = sum(report.tension_summary.values())
                print(f"   Tensions identified: {total_tensions}", file=sys.stderr)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_version(args: argparse.Namespace) -> int:
    """Execute the version command."""
    from flakes import __version__
    print(f"flakes version {__version__}")
    return 0


def main() -> NoReturn:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    if args.command == "version":
        sys.exit(cmd_version(args))
    elif args.command == "analyze":
        sys.exit(asyncio.run(cmd_analyze(args)))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
>>>>>>> ce7ed15 (feat: Add comprehensive CLI interface):flakes/cli.py
