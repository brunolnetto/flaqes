"""
Intent specification for schema analysis.

Intent is the crucial input that makes flaqes' advice meaningful.
Without knowing what the schema is optimized for, any recommendation
is just generic "best practice" noise.
"""

from dataclasses import dataclass, field

from flaqes.core.types import (
    ConsistencyLevel,
    DataVolume,
    Engine,
    EvolutionRate,
    ReadPattern,
    Workload,
    WriteFrequency,
)


@dataclass(frozen=True, slots=True)
class Intent:
    """
    User-declared intent for database schema analysis.

    This captures what the schema is optimized for, enabling flaqes
    to provide contextual advice rather than generic recommendations.

    All fields have sensible defaults, but more specific intent leads
    to more relevant analysis.

    Example:
        >>> intent = Intent(
        ...     workload="OLAP",
        ...     write_frequency="low",
        ...     read_patterns=["aggregation", "range_scan"],
        ...     evolution_rate="high",
        ...     data_volume="large",
        ... )
    """

    workload: Workload = "mixed"
    """Primary workload type: OLTP, OLAP, or mixed."""

    write_frequency: WriteFrequency = "medium"
    """How often data is written: high, medium, or low."""

    read_patterns: tuple[ReadPattern, ...] = field(
        default_factory=lambda: ("point_lookup",)
    )
    """
    Common read access patterns. Order indicates priority.
    Options: point_lookup, range_scan, aggregation, join_heavy.
    """

    consistency: ConsistencyLevel = "strong"
    """Required consistency level: strong or eventual."""

    evolution_rate: EvolutionRate = "medium"
    """How often schema changes: high, medium, low, or frozen."""

    data_volume: DataVolume = "medium"
    """
    Approximate data volume classification:
    - small: < 100K rows
    - medium: 100K - 10M rows
    - large: 10M - 1B rows
    - massive: > 1B rows
    """

    engine: Engine = "postgresql"
    """Target database engine. PostgreSQL only for v1."""

    def __post_init__(self) -> None:
        """Validate intent values."""
        # Ensure read_patterns is a tuple (in case user passes a list)
        if isinstance(self.read_patterns, list):
            object.__setattr__(self, "read_patterns", tuple(self.read_patterns))

    @property
    def is_write_heavy(self) -> bool:
        """Check if workload is write-heavy."""
        return self.write_frequency == "high"

    @property
    def is_read_heavy(self) -> bool:
        """Check if workload favors reads."""
        return self.write_frequency == "low" or self.workload == "OLAP"

    @property
    def is_analytical(self) -> bool:
        """Check if workload is analytical."""
        return self.workload == "OLAP" or "aggregation" in self.read_patterns

    @property
    def is_transactional(self) -> bool:
        """Check if workload is transactional."""
        return self.workload == "OLTP" and self.consistency == "strong"

    @property
    def expects_schema_changes(self) -> bool:
        """Check if schema is expected to evolve frequently."""
        return self.evolution_rate in ("high", "medium")

    @property
    def is_high_volume(self) -> bool:
        """Check if data volume is large or massive."""
        return self.data_volume in ("large", "massive")

    def summary(self) -> str:
        """Return a human-readable summary of the intent."""
        patterns = ", ".join(self.read_patterns)
        return (
            f"Workload: {self.workload} | "
            f"Writes: {self.write_frequency} | "
            f"Reads: {patterns} | "
            f"Volume: {self.data_volume} | "
            f"Evolution: {self.evolution_rate}"
        )


# Predefined intent profiles for common scenarios
OLTP_INTENT = Intent(
    workload="OLTP",
    write_frequency="high",
    read_patterns=("point_lookup",),
    consistency="strong",
    evolution_rate="low",
    data_volume="medium",
)

OLAP_INTENT = Intent(
    workload="OLAP",
    write_frequency="low",
    read_patterns=("aggregation", "range_scan"),
    consistency="eventual",
    evolution_rate="low",
    data_volume="large",
)

EVENT_SOURCING_INTENT = Intent(
    workload="mixed",
    write_frequency="high",
    read_patterns=("range_scan", "aggregation"),
    consistency="strong",
    evolution_rate="medium",
    data_volume="large",
)

STARTUP_MVP_INTENT = Intent(
    workload="mixed",
    write_frequency="medium",
    read_patterns=("point_lookup", "join_heavy"),
    consistency="strong",
    evolution_rate="high",
    data_volume="small",
)
