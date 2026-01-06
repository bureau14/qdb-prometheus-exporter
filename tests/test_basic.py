import pytest
import logging

from qdb_prometheus_exporter.stats import fetch_qdb_stats
from qdb_prometheus_exporter.collector import QdbStatsCollector

logger = logging.getLogger(__name__)


def test_fetch_qdb_stats(qdbd_settings):
    """ "
    Tests if fetch_qdb_stats function retrieves statistics from QuasarDB.
    """
    stats = fetch_qdb_stats(qdbd_settings.get("secure"), None, None, logger)

    for node_id in stats.keys():
        # node_id is ip:port, uri is qdb://ip:port
        assert node_id in qdbd_settings.get("secure").get("uri")

        assert "by_uid" in stats[node_id]
        assert "cumulative" in stats[node_id]


def test_collector_collect(qdbd_settings):
    """
    Tests if Prometheus collector returns metrics with expected labels.
    """
    collector = QdbStatsCollector(qdbd_settings.get("secure"), None, None, logger)
    metrics = list(collector.collect())

    assert len(metrics) > 0

    found = False
    for metric in metrics:
        for sample in metric.samples:
            if "endpoint" in sample.labels and "stat_type" in sample.labels:
                found = True
                break
        if found:
            break

    assert found, "No metric with expected labels 'endpoint' and 'stat_type' found."
