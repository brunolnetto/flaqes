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
