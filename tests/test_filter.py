import pytest
import logging
from qdb_prometheus_exporter.stats import filter_stats

logger = logging.getLogger(__name__)


def test_filter_single_include(stats):
    stats_ = filter_stats(stats, [r"memory\."], None, logger)

    assert stats_ != stats

    for node_id in stats_:
        for metric_name in stats_[node_id]["cumulative"]:
            assert "memory." in metric_name

        for uid in stats_[node_id]["by_uid"]:
            for metric_name in stats_[node_id]["by_uid"][uid]:
                assert "memory." in metric_name


def test_filter_multiple_include(stats):
    stats_ = filter_stats(stats, [r"memory\.", r"network\."], None, logger)

    assert stats_ != stats

    # Also ensure that the result is actually different now that we also allow "network" to be returned
    assert stats_ != filter_stats(stats, [r"memory\."], None, logger)

    for node_id in stats_:
        for metric_name in stats_[node_id]["cumulative"]:
            assert "memory." in metric_name or "network." in metric_name

        for uid in stats_[node_id]["by_uid"]:
            for metric_name in stats_[node_id]["by_uid"][uid]:
                assert "memory." in metric_name or "network." in metric_name


def test_filter_single_exclude(stats):
    stats_ = filter_stats(stats, None, [r"memory\."], logger)

    assert stats_ != stats

    for node_id in stats_:
        for metric_name in stats_[node_id]["cumulative"]:
            assert "memory." not in metric_name

        for uid in stats_[node_id]["by_uid"]:
            for metric_name in stats_[node_id]["by_uid"][uid]:
                assert "memory." not in metric_name


def test_filter_multiple_exclude(stats):
    stats_ = filter_stats(stats, None, [r"memory\.", r"network\."], logger)

    assert stats_ != stats

    # Also ensure that the result is actually different now that we also allow "network" to be returned
    assert stats_ != filter_stats(stats, None, [r"memory\."], logger)
    assert stats_ != filter_stats(stats, [r"memory\."], None, logger)
    assert stats_ != filter_stats(stats, [r"memory\.", r"network\."], None, logger)

    for node_id in stats_:
        for metric_name in stats_[node_id]["cumulative"]:
            assert "memory." not in metric_name
            assert "network." not in metric_name

        for uid in stats_[node_id]["by_uid"]:
            for metric_name in stats_[node_id]["by_uid"][uid]:
                assert "memory." not in metric_name
                assert "network." not in metric_name
