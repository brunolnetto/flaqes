"""
Command-line interface for flaqes.

Provides commands for analyzing database schemas.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import TYPE_CHECKING

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
        version="%(prog)s 0.1.0",
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
        help="Default schema name when not specified in DDL (default: public)",
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
    elif args.command == "introspect":
        return asyncio.run(run_introspect(args))
    elif args.command == "diagram":
        return asyncio.run(run_diagram(args))
    
    parser.print_help()  # pragma: no cover
    return 0  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

