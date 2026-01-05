import pytest
import logging

from qdb_prometheus_exporter.stats import fetch_qdb_stats

logger = logging.getLogger(__name__)


def test_get_stats(qdbd_settings):
    stats = fetch_qdb_stats(qdbd_settings.get("secure"), None, None, logger)

    for node_id in stats.keys():
        # node_id is ip:port, uri is qdb://ip:port
        assert node_id in qdbd_settings.get("uri")

        assert "by_uid" in stats[node_id]
        assert "cumulative" in stats[node_id]
