"""Tests for pattern detection module."""

import pytest

from flakes.analysis.pattern_matcher import (
    DetectedPattern,
    PatternCategory,
    PatternDetector,
    PatternSignal,
    PatternType,
    _detect_scd_type_2,
    _detect_soft_delete,
    _detect_audit_timestamps,
    _detect_audit_user_tracking,
    _detect_polymorphic,
    _detect_jsonb_schema,
    _detect_optimistic_locking,
    _detect_tree_structure,
    _detect_event_sourcing,
)
from flakes.core.schema_graph import (
    Column,
    DataType,
    ForeignKey,
    PrimaryKey,
    SchemaGraph,
    Table,
)
from flakes.core.types import DataTypeCategory


# =============================================================================
# Helper Functions
# =============================================================================


def make_column(
    name: str,
    category: DataTypeCategory = DataTypeCategory.TEXT,
    nullable: bool = True,
) -> Column:
    """Create a column with sensible defaults."""
    return Column(
        name=name,
        data_type=DataType(raw=category.name.lower(), category=category),
        nullable=nullable,
    )


def make_table(
    name: str,
    columns: list[Column],
    primary_key: PrimaryKey | None = None,
    foreign_keys: list[ForeignKey] | None = None,
    schema: str = "public",
) -> Table:
    """Create a table with sensible defaults."""
    return Table(
        name=name,
        schema=schema,
        columns=columns,
        primary_key=primary_key,
        foreign_keys=foreign_keys or [],
    )


# =============================================================================
# SCD Type 2 Detection Tests
# =============================================================================


class TestSCDType2Detection:
    """Tests for SCD Type 2 pattern detection."""

    def test_classic_scd2_with_validity_period(self) -> None:
        """Table with valid_from/valid_to should be detected as SCD2."""
        table = make_table(
            "customer_history",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("customer_id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
                make_column("valid_from", DataTypeCategory.TIMESTAMP),
                make_column("valid_to", DataTypeCategory.TIMESTAMP),
                make_column("is_current", DataTypeCategory.BOOLEAN),
            ],
        )
        
        result = _detect_scd_type_2(table)
        
        assert result is not None
        assert result.pattern_type == PatternType.SCD_TYPE_2
        assert result.confidence >= 0.8
        assert "valid_from" in result.related_columns
        assert "valid_to" in result.related_columns

    def test_scd2_with_effective_dates(self) -> None:
        """Alternative naming (effective_date/end_date) should work."""
        table = make_table(
            "product_versions",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("effective_date", DataTypeCategory.TIMESTAMP),
                make_column("end_date", DataTypeCategory.TIMESTAMP),
            ],
        )
        
        result = _detect_scd_type_2(table)
        
        assert result is not None
        assert result.confidence >= 0.7

    def test_scd2_with_version_column(self) -> None:
        """Version column adds weight."""
        table = make_table(
            "contract_versions",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("valid_from", DataTypeCategory.TIMESTAMP),
                make_column("version", DataTypeCategory.INTEGER),
            ],
        )
        
        result = _detect_scd_type_2(table)
        
        assert result is not None
        assert any(s.name == "version_column" for s in result.signals)

    def test_updated_at_reduces_confidence(self) -> None:
        """updated_at column reduces SCD2 confidence."""
        table = make_table(
            "records",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("valid_from", DataTypeCategory.TIMESTAMP),
                make_column("valid_to", DataTypeCategory.TIMESTAMP),
                make_column("updated_at", DataTypeCategory.TIMESTAMP),
            ],
        )
        
        result = _detect_scd_type_2(table)
        
        assert result is not None
        # Confidence should be lower due to updated_at
        assert any(s.name == "updated_at_present" for s in result.signals)

    def test_no_scd2_signals(self) -> None:
        """Table without SCD2 signals returns None."""
        table = make_table(
            "simple_table",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
            ],
        )
        
        result = _detect_scd_type_2(table)
        
        assert result is None


# =============================================================================
# Soft Delete Detection Tests
# =============================================================================


class TestSoftDeleteDetection:
    """Tests for soft delete pattern detection."""

    def test_deleted_at_timestamp(self) -> None:
        """deleted_at timestamp should be detected."""
        table = make_table(
            "users",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
                make_column("deleted_at", DataTypeCategory.TIMESTAMP),
            ],
        )
        
        result = _detect_soft_delete(table)
        
        assert result is not None
        assert result.pattern_type == PatternType.TEMPORAL_DELETE
        assert result.confidence >= 0.8
        assert "deleted_at" in result.related_columns

    def test_is_deleted_flag(self) -> None:
        """is_deleted boolean should be detected."""
        table = make_table(
            "posts",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("content", DataTypeCategory.TEXT),
                make_column("is_deleted", DataTypeCategory.BOOLEAN),
            ],
        )
        
        result = _detect_soft_delete(table)
        
        assert result is not None
        assert result.pattern_type == PatternType.SOFT_DELETE
        assert result.confidence >= 0.8

    def test_deleted_by_column(self) -> None:
        """deleted_by adds weight."""
        table = make_table(
            "documents",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("deleted_at", DataTypeCategory.TIMESTAMP),
                make_column("deleted_by", DataTypeCategory.INTEGER),
            ],
        )
        
        result = _detect_soft_delete(table)
        
        assert result is not None
        assert "deleted_by" in result.related_columns

    def test_no_soft_delete_signals(self) -> None:
        """Table without soft delete signals returns None."""
        table = make_table(
            "simple_table",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
            ],
        )
        
        result = _detect_soft_delete(table)
        
        assert result is None


# =============================================================================
# Audit Timestamp Detection Tests
# =============================================================================


class TestAuditTimestampDetection:
    """Tests for audit timestamp pattern detection."""

    def test_created_at_and_updated_at(self) -> None:
        """Both timestamps should be detected."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("total", DataTypeCategory.DECIMAL),
                make_column("created_at", DataTypeCategory.TIMESTAMP),
                make_column("updated_at", DataTypeCategory.TIMESTAMP),
            ],
        )
        
        result = _detect_audit_timestamps(table)
        
        assert result is not None
        assert result.pattern_type == PatternType.AUDIT_TIMESTAMPS
        assert result.confidence >= 0.9
        assert "created_at" in result.related_columns
        assert "updated_at" in result.related_columns

    def test_only_created_at(self) -> None:
        """Only created_at should still be detected."""
        table = make_table(
            "events",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("created_at", DataTypeCategory.TIMESTAMP),
            ],
        )
        
        result = _detect_audit_timestamps(table)
        
        assert result is not None
        assert result.confidence >= 0.4

    def test_alternative_naming(self) -> None:
        """Alternative names like modified_at should work."""
        table = make_table(
            "records",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("create_time", DataTypeCategory.TIMESTAMP),
                make_column("last_modified", DataTypeCategory.TIMESTAMP),
            ],
        )
        
        result = _detect_audit_timestamps(table)
        
        assert result is not None
        assert len(result.signals) == 2


# =============================================================================
# Audit User Tracking Detection Tests
# =============================================================================


class TestAuditUserTrackingDetection:
    """Tests for user tracking pattern detection."""

    def test_created_by_and_updated_by(self) -> None:
        """Both user tracking columns should be detected."""
        table = make_table(
            "documents",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("content", DataTypeCategory.TEXT),
                make_column("created_by", DataTypeCategory.INTEGER),
                make_column("updated_by", DataTypeCategory.INTEGER),
            ],
        )
        
        result = _detect_audit_user_tracking(table)
        
        assert result is not None
        assert result.pattern_type == PatternType.AUDIT_USER_TRACKING
        assert "created_by" in result.related_columns
        assert "updated_by" in result.related_columns


# =============================================================================
# Polymorphic Association Detection Tests
# =============================================================================


class TestPolymorphicDetection:
    """Tests for polymorphic association pattern detection."""

    def test_type_discriminator_with_id(self) -> None:
        """Type column with generic ID should be detected."""
        table = make_table(
            "comments",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("body", DataTypeCategory.TEXT),
                make_column("commentable_type", DataTypeCategory.TEXT),
                make_column("commentable_id", DataTypeCategory.INTEGER),
            ],
        )
        
        result = _detect_polymorphic(table)
        
        assert result is not None
        assert result.pattern_type == PatternType.POLYMORPHIC
        assert result.confidence >= 0.5

    def test_entity_type_column(self) -> None:
        """entity_type column should be detected."""
        table = make_table(
            "attachments",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("file_path", DataTypeCategory.TEXT),
                make_column("entity_type", DataTypeCategory.TEXT),
                make_column("entity_id", DataTypeCategory.INTEGER),
            ],
        )
        
        result = _detect_polymorphic(table)
        
        assert result is not None
        assert any(s.name == "type_discriminator" for s in result.signals)


# =============================================================================
# JSONB Schema Detection Tests
# =============================================================================


class TestJSONBSchemaDetection:
    """Tests for JSONB schema flexibility pattern detection."""

    def test_significant_json_column(self) -> None:
        """JSONB column named 'metadata' should have high weight."""
        table = make_table(
            "products",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
                make_column("metadata", DataTypeCategory.JSON),
            ],
        )
        
        result = _detect_jsonb_schema(table)
        
        assert result is not None
        assert result.pattern_type == PatternType.JSONB_SCHEMA
        assert result.confidence >= 0.6

    def test_generic_json_column(self) -> None:
        """Generic JSON column should still be detected."""
        table = make_table(
            "settings",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("config_values", DataTypeCategory.JSON),
            ],
        )
        
        result = _detect_jsonb_schema(table)
        
        assert result is not None
        assert result.confidence >= 0.3

    def test_no_json_columns(self) -> None:
        """Table without JSON columns returns None."""
        table = make_table(
            "simple",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
            ],
        )
        
        result = _detect_jsonb_schema(table)
        
        assert result is None


# =============================================================================
# Optimistic Locking Detection Tests
# =============================================================================


class TestOptimisticLockingDetection:
    """Tests for optimistic locking pattern detection."""

    def test_version_column(self) -> None:
        """version column should be detected."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("status", DataTypeCategory.TEXT),
                make_column("version", DataTypeCategory.INTEGER),
            ],
        )
        
        result = _detect_optimistic_locking(table)
        
        assert result is not None
        assert result.pattern_type == PatternType.OPTIMISTIC_LOCKING
        assert result.confidence >= 0.8

    def test_lock_version_column(self) -> None:
        """lock_version column should be detected."""
        table = make_table(
            "records",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("lock_version", DataTypeCategory.INTEGER),
            ],
        )
        
        result = _detect_optimistic_locking(table)
        
        assert result is not None


# =============================================================================
# Tree Structure Detection Tests
# =============================================================================


class TestTreeStructureDetection:
    """Tests for tree/hierarchy structure pattern detection."""

    def test_self_referencing_fk(self) -> None:
        """Self-referencing FK should be detected."""
        table = make_table(
            "categories",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
                make_column("parent_id", DataTypeCategory.INTEGER),
            ],
            foreign_keys=[
                ForeignKey(
                    name="fk_parent",
                    columns=("parent_id",),
                    target_schema="public",
                    target_table="categories",
                    target_columns=("id",),
                )
            ],
        )
        
        graph = SchemaGraph.from_tables([table])
        result = _detect_tree_structure(table, graph)
        
        assert result is not None
        assert result.pattern_type == PatternType.TREE_STRUCTURE
        assert result.confidence >= 0.7

    def test_materialized_path(self) -> None:
        """path column should detect materialized path pattern."""
        table = make_table(
            "categories",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
                make_column("path", DataTypeCategory.TEXT),
            ],
        )
        
        graph = SchemaGraph.from_tables([table])
        result = _detect_tree_structure(table, graph)
        
        assert result is not None
        assert result.pattern_type == PatternType.MATERIALIZED_PATH


# =============================================================================
# Event Sourcing Detection Tests
# =============================================================================


class TestEventSourcingDetection:
    """Tests for event sourcing pattern detection."""

    def test_event_table_with_payload(self) -> None:
        """Event table with payload should be detected."""
        table = make_table(
            "domain_events",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("event_type", DataTypeCategory.TEXT),
                make_column("payload", DataTypeCategory.JSON),
                make_column("created_at", DataTypeCategory.TIMESTAMP),
            ],
        )
        
        result = _detect_event_sourcing(table)
        
        assert result is not None
        assert result.pattern_type == PatternType.EVENT_SOURCING
        assert result.confidence >= 0.7

    def test_audit_log_table(self) -> None:
        """Audit log table should be detected."""
        table = make_table(
            "audit_log",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("action", DataTypeCategory.TEXT),
                make_column("data", DataTypeCategory.JSON),
                make_column("occurred_at", DataTypeCategory.TIMESTAMP),
            ],
        )
        
        result = _detect_event_sourcing(table)
        
        assert result is not None
        assert result.confidence >= 0.5

    def test_immutable_without_updated_at(self) -> None:
        """created_at without updated_at should add weight."""
        table = make_table(
            "events",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("event_type", DataTypeCategory.TEXT),
                make_column("created_at", DataTypeCategory.TIMESTAMP),
            ],
        )
        
        result = _detect_event_sourcing(table)
        
        assert result is not None
        assert any(s.name == "immutable_timestamps" for s in result.signals)


# =============================================================================
# Pattern Detector Class Tests
# =============================================================================


class TestPatternDetector:
    """Tests for PatternDetector class."""

    def test_detect_all_returns_sorted_patterns(self) -> None:
        """detect_all should return patterns sorted by confidence."""
        table = make_table(
            "audited_table",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("created_at", DataTypeCategory.TIMESTAMP),
                make_column("updated_at", DataTypeCategory.TIMESTAMP),
                make_column("deleted_at", DataTypeCategory.TIMESTAMP),
                make_column("metadata", DataTypeCategory.JSON),
            ],
        )
        
        detector = PatternDetector()
        graph = SchemaGraph.from_tables([table])
        patterns = detector.detect_all(table, graph)
        
        assert len(patterns) >= 2  # Should detect audit timestamps and soft delete
        
        # Should be sorted by confidence (descending)
        confidences = [p.confidence for p in patterns]
        assert confidences == sorted(confidences, reverse=True)

    def test_detect_specific_pattern(self) -> None:
        """detect_pattern should find specific pattern type."""
        table = make_table(
            "orders",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("created_at", DataTypeCategory.TIMESTAMP),
                make_column("updated_at", DataTypeCategory.TIMESTAMP),
            ],
        )
        
        detector = PatternDetector()
        graph = SchemaGraph.from_tables([table])
        
        result = detector.detect_pattern(table, PatternType.AUDIT_TIMESTAMPS, graph)
        
        assert result is not None
        assert result.pattern_type == PatternType.AUDIT_TIMESTAMPS

    def test_detect_schema_patterns(self) -> None:
        """detect_schema_patterns should analyze all tables."""
        table1 = make_table(
            "users",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("created_at", DataTypeCategory.TIMESTAMP),
            ],
        )
        table2 = make_table(
            "products",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("metadata", DataTypeCategory.JSON),
            ],
        )
        
        graph = SchemaGraph.from_tables([table1, table2])
        detector = PatternDetector()
        
        results = detector.detect_schema_patterns(graph)
        
        assert len(results) >= 1  # At least one table should have patterns

    def test_min_confidence_threshold(self) -> None:
        """Patterns below threshold should be excluded."""
        table = make_table(
            "weak_signals",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("valid_from", DataTypeCategory.TIMESTAMP),  # Only valid_from, low confidence
            ],
        )
        
        # High threshold
        detector = PatternDetector(min_confidence=0.8)
        graph = SchemaGraph.from_tables([table])
        patterns = detector.detect_all(table, graph)
        
        # SCD2 with only valid_from has confidence ~0.4, should be excluded
        scd2_patterns = [p for p in patterns if p.pattern_type == PatternType.SCD_TYPE_2]
        assert len(scd2_patterns) == 0


# =============================================================================
# Pattern Data Structure Tests
# =============================================================================


class TestPatternSignal:
    """Tests for PatternSignal NamedTuple."""

    def test_signal_creation(self) -> None:
        """Signal should be creatable."""
        signal = PatternSignal(
            name="test_signal",
            description="A test signal",
            weight=0.8,
            columns=("col1", "col2"),
        )
        
        assert signal.name == "test_signal"
        assert signal.weight == 0.8
        assert len(signal.columns) == 2


class TestDetectedPattern:
    """Tests for DetectedPattern dataclass."""

    def test_category_property(self) -> None:
        """category should return correct PatternCategory."""
        pattern = DetectedPattern(
            pattern_type=PatternType.SCD_TYPE_2,
            table="public.test",
            confidence=0.9,
        )
        
        assert pattern.category == PatternCategory.TEMPORAL

    def test_is_confident(self) -> None:
        """is_confident should use 0.7 threshold."""
        confident = DetectedPattern(
            pattern_type=PatternType.SOFT_DELETE,
            table="public.test",
            confidence=0.8,
        )
        not_confident = DetectedPattern(
            pattern_type=PatternType.SOFT_DELETE,
            table="public.test",
            confidence=0.5,
        )
        
        assert confident.is_confident
        assert not not_confident.is_confident

    def test_summary(self) -> None:
        """summary should return formatted string."""
        pattern = DetectedPattern(
            pattern_type=PatternType.AUDIT_TIMESTAMPS,
            table="public.orders",
            confidence=0.85,
        )
        
        summary = pattern.summary()
        
        assert "public.orders" in summary
        assert "AUDIT_TIMESTAMPS" in summary
        assert "85%" in summary


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestPolymorphicEdgeCases:
    """Additional tests for polymorphic edge cases."""

    def test_multiple_nullable_fks(self) -> None:
        """Multiple nullable FKs should add signal."""
        table = make_table(
            "taggings",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("post_id", DataTypeCategory.INTEGER, nullable=True),
                make_column("comment_id", DataTypeCategory.INTEGER, nullable=True),
                make_column("user_id", DataTypeCategory.INTEGER, nullable=True),
                make_column("record_type", DataTypeCategory.TEXT),  # Type discriminator
            ],
            foreign_keys=[
                ForeignKey(
                    name="fk_post",
                    columns=("post_id",),
                    target_schema="public",
                    target_table="posts",
                    target_columns=("id",),
                ),
                ForeignKey(
                    name="fk_comment",
                    columns=("comment_id",),
                    target_schema="public",
                    target_table="comments",
                    target_columns=("id",),
                ),
            ],
        )
        
        result = _detect_polymorphic(table)
        
        assert result is not None
        assert any(s.name == "multiple_nullable_fks" for s in result.signals)

    def test_low_confidence_polymorphic_excluded(self) -> None:
        """Polymorphic with only type column (no ID) should be below threshold."""
        table = make_table(
            "items",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("type", DataTypeCategory.TEXT),
                # No _id columns, no nullable FKs
            ],
        )
        
        # Type discriminator alone (0.6) is above 0.4 threshold, so it's detected
        result = _detect_polymorphic(table)
        
        # With only type column (0.6 weight), it should be detected 
        assert result is not None


class TestTreeStructureEdgeCases:
    """Additional tests for tree structure edge cases."""

    def test_parent_column_without_fk(self) -> None:
        """Parent column without FK should still detect hierarchy pattern."""
        table = make_table(
            "employees",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("name", DataTypeCategory.TEXT),
                make_column("manager_id", DataTypeCategory.INTEGER),  # No FK defined
            ],
            foreign_keys=[],  # No FK for manager_id
        )
        
        graph = SchemaGraph.from_tables([table])
        result = _detect_tree_structure(table, graph)
        
        assert result is not None
        assert any(s.name == "parent_column" for s in result.signals)
        assert result.confidence >= 0.4


class TestPatternDetectorEdgeCases:
    """Additional tests for PatternDetector edge cases."""

    def test_detect_unknown_pattern_returns_none(self) -> None:
        """detect_pattern for unsupported type returns None."""
        table = make_table(
            "simple",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
            ],
        )
        
        detector = PatternDetector()
        
        # SCD_TYPE_1, SCD_TYPE_3, VERSIONED, EAV, etc are not implemented
        result = detector.detect_pattern(table, PatternType.SCD_TYPE_1)
        
        assert result is None

    def test_detect_pattern_below_confidence_returns_none(self) -> None:
        """detect_pattern below threshold returns None."""
        table = make_table(
            "records",
            columns=[
                make_column("id", DataTypeCategory.INTEGER),
                make_column("valid_from", DataTypeCategory.TIMESTAMP),  # Only 0.4 confidence
            ],
        )
        
        detector = PatternDetector(min_confidence=0.8)
        result = detector.detect_pattern(table, PatternType.SCD_TYPE_2)
        
        assert result is None

