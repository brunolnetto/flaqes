"""Tests for Intent dataclass."""

import pytest

from flaqes.core.intent import (
    EVENT_SOURCING_INTENT,
    OLAP_INTENT,
    OLTP_INTENT,
    STARTUP_MVP_INTENT,
    Intent,
)


class TestIntentDefaults:
    """Tests for Intent default values."""

    def test_default_intent_is_balanced(self) -> None:
        intent = Intent()
        assert intent.workload == "mixed"
        assert intent.write_frequency == "medium"
        assert intent.consistency == "strong"
        assert intent.evolution_rate == "medium"
        assert intent.data_volume == "medium"
        assert intent.engine == "postgresql"

    def test_default_read_patterns(self) -> None:
        intent = Intent()
        assert intent.read_patterns == ("point_lookup",)


class TestIntentCreation:
    """Tests for Intent instantiation."""

    def test_create_olap_intent(self) -> None:
        intent = Intent(
            workload="OLAP",
            write_frequency="low",
            read_patterns=("aggregation", "range_scan"),
            consistency="eventual",
            evolution_rate="low",
            data_volume="large",
        )
        assert intent.workload == "OLAP"
        assert intent.is_analytical

    def test_create_oltp_intent(self) -> None:
        intent = Intent(
            workload="OLTP",
            write_frequency="high",
            read_patterns=("point_lookup",),
            consistency="strong",
        )
        assert intent.workload == "OLTP"
        assert intent.is_transactional

    def test_list_read_patterns_converted_to_tuple(self) -> None:
        intent = Intent(read_patterns=["aggregation", "join_heavy"])  # type: ignore
        assert intent.read_patterns == ("aggregation", "join_heavy")
        assert isinstance(intent.read_patterns, tuple)


class TestIntentProperties:
    """Tests for Intent computed properties."""

    def test_is_write_heavy(self) -> None:
        heavy = Intent(write_frequency="high")
        medium = Intent(write_frequency="medium")
        low = Intent(write_frequency="low")

        assert heavy.is_write_heavy
        assert not medium.is_write_heavy
        assert not low.is_write_heavy

    def test_is_read_heavy(self) -> None:
        olap = Intent(workload="OLAP")
        low_writes = Intent(write_frequency="low")
        high_writes = Intent(workload="OLTP", write_frequency="high")

        assert olap.is_read_heavy
        assert low_writes.is_read_heavy
        assert not high_writes.is_read_heavy

    def test_is_analytical(self) -> None:
        olap = Intent(workload="OLAP")
        agg = Intent(read_patterns=("aggregation",))
        oltp = Intent(workload="OLTP", read_patterns=("point_lookup",))

        assert olap.is_analytical
        assert agg.is_analytical
        assert not oltp.is_analytical

    def test_is_transactional(self) -> None:
        oltp_strong = Intent(workload="OLTP", consistency="strong")
        oltp_eventual = Intent(workload="OLTP", consistency="eventual")
        olap = Intent(workload="OLAP", consistency="strong")

        assert oltp_strong.is_transactional
        assert not oltp_eventual.is_transactional
        assert not olap.is_transactional

    def test_expects_schema_changes(self) -> None:
        high = Intent(evolution_rate="high")
        medium = Intent(evolution_rate="medium")
        low = Intent(evolution_rate="low")
        frozen = Intent(evolution_rate="frozen")

        assert high.expects_schema_changes
        assert medium.expects_schema_changes
        assert not low.expects_schema_changes
        assert not frozen.expects_schema_changes

    def test_is_high_volume(self) -> None:
        large = Intent(data_volume="large")
        massive = Intent(data_volume="massive")
        medium = Intent(data_volume="medium")
        small = Intent(data_volume="small")

        assert large.is_high_volume
        assert massive.is_high_volume
        assert not medium.is_high_volume
        assert not small.is_high_volume


class TestIntentSummary:
    """Tests for Intent summary method."""

    def test_summary_includes_all_key_fields(self) -> None:
        intent = Intent(
            workload="OLAP",
            write_frequency="low",
            read_patterns=("aggregation",),
            data_volume="large",
            evolution_rate="low",
        )
        summary = intent.summary()

        assert "OLAP" in summary
        assert "low" in summary
        assert "aggregation" in summary
        assert "large" in summary


class TestIntentImmutability:
    """Tests for Intent immutability (frozen dataclass)."""

    def test_intent_is_frozen(self) -> None:
        intent = Intent()
        with pytest.raises(AttributeError):
            intent.workload = "OLAP"  # type: ignore


class TestPredefinedIntents:
    """Tests for predefined intent profiles."""

    def test_oltp_intent(self) -> None:
        assert OLTP_INTENT.workload == "OLTP"
        assert OLTP_INTENT.is_transactional
        assert OLTP_INTENT.is_write_heavy

    def test_olap_intent(self) -> None:
        assert OLAP_INTENT.workload == "OLAP"
        assert OLAP_INTENT.is_analytical
        assert OLAP_INTENT.is_read_heavy

    def test_event_sourcing_intent(self) -> None:
        assert EVENT_SOURCING_INTENT.is_write_heavy
        assert EVENT_SOURCING_INTENT.is_high_volume

    def test_startup_mvp_intent(self) -> None:
        assert STARTUP_MVP_INTENT.expects_schema_changes
        assert not STARTUP_MVP_INTENT.is_high_volume
