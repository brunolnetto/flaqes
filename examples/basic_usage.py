"""
Example: Analyze a PostgreSQL database schema

This example shows how to use flaqes to analyze a database schema
and generate a comprehensive report.

Requirements:
- PostgreSQL database running
- asyncpg installed (pip install flaqes[postgresql])
"""

import asyncio
import json

from flaqes import Intent, analyze_schema


async def main():
    # Example 1: OLAP workload
    print("=" * 60)
    print("Example 1: OLAP Data Warehouse Analysis")
    print("=" * 60)

    olap_intent = Intent(
        workload="OLAP",
        write_frequency="low",
        read_patterns=["aggregation", "range_scan"],
        data_volume="large",
        evolution_rate="low",
    )

    # Replace with your database connection string
    dsn = "postgresql://user:password@localhost:5432/your_database"

    try:
        report = await analyze_schema(dsn=dsn, intent=olap_intent)

        print(f"\nAnalyzed {report.table_count} tables")
        print(f"\nIntent: {olap_intent.summary()}")
        print("\n" + "=" * 60)
        print("MARKDOWN REPORT")
        print("=" * 60)
        print(report.to_markdown())

        # Save to file
        with open("schema_report.md", "w") as f:
            f.write(report.to_markdown())
        print("\n✅ Report saved to schema_report.md")

        # Also save JSON version
        with open("schema_report.json", "w") as f:
            json.dump(report.to_dict(), f, indent=2)
        print("✅ JSON report saved to schema_report.json")

    except Exception as e:
        print(f"❌ Error: {e}")
        print(
            "\nNote: Make sure to update the DSN with your database connection details."
        )

    print("\n" + "=" * 60)
    print("Example 2: OLTP Application Analysis")
    print("=" * 60)

    oltp_intent = Intent(
        workload="OLTP",
        write_frequency="high",
        read_patterns=["point_lookup", "join_heavy"],
        data_volume="medium",
        evolution_rate="high",
    )

    print(f"\nIntent: {oltp_intent.summary()}")
    print("This would provide different insights focused on:")
    print("- Write performance optimization")
    print("- Index efficiency for point lookups")
    print("- Schema flexibility for rapid evolution")

    print("\n" + "=" * 60)
    print("Example 3: Specific Tables Only")
    print("=" * 60)

    # Analyze specific tables
    try:
        report = await analyze_schema(
            dsn=dsn,
            intent=oltp_intent,
            tables=["users", "orders", "products"],  # Only these tables
        )
        print(f"\n✅ Analyzed {report.table_count} specific tables")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                    flaqes Example Usage                        ║
    ║             A Schema Critic for PostgreSQL                     ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)

    asyncio.run(main())
