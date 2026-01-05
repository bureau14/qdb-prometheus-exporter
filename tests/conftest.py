import datetime
import logging

import pytest
import quasardb

from qdb_prometheus_exporter.stats import fetch_qdb_stats


def connect(**kwargs):
    return quasardb.Cluster(**kwargs)


def config():
    return {
        "uri": {"insecure": "qdb://127.0.0.1:2836", "secure": "qdb://127.0.0.1:2838"}
    }


def _qdbd_settings():
    return {
        "insecure": {
            "uri": "qdb://127.0.0.1:2836",
        },
        "secure": {
            "uri": "qdb://127.0.0.1:2838",
            "user_private_key_file": "user_private.key",
            "cluster_public_key_file": "cluster_public.key",
        },
    }


@pytest.fixture(scope="module")
def qdbd_settings():
    return _qdbd_settings()


@pytest.fixture(scope="module")
def qdbd_connection(qdbd_settings):
    for security, args in qdbd_settings.items():
        conn = connect(**args)
        conn.purge_all(datetime.timedelta(minutes=1))
        yield conn
        conn.close()


@pytest.fixture(scope="module")
def stats(qdbd_settings):
    for security, args in qdbd_settings.items():
        yield fetch_qdb_stats(args, None, None, logging.getLogger(__name__))
